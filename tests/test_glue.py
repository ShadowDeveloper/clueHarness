"""Glue coverage: CLI commands (CliRunner), YAML config, eval report, human CLI agent, live-eval runner (mock)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clue.__main__ import app
from clue.agents.factory import make_agent, parse_players_arg
from clue.agents.human import HumanCLIAgent, describe_event
from clue.config import load_yaml_config
from clue.eval.live_eval import run_live_eval
from clue.eval.report import run_eval
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game

runner = CliRunner()


# ------------------------------------------------------------------ CLI
def test_cli_play_cli_ui_writes_replay(tmp_path: Path) -> None:
    res = runner.invoke(app, ["play", "--players", "baseline:expert,baseline,llm:aggressive", "--seed", "3", "--ui", "cli", "--quiet", "--replay-dir", str(tmp_path)])
    assert res.exit_code == 0, res.output
    files = list(tmp_path.glob("*.jsonl"))
    assert files, res.output
    res2 = runner.invoke(app, ["replay", str(files[0])])
    assert res2.exit_code == 0 and "GAME OVER" in res2.output


def test_cli_play_from_yaml_and_overrides(tmp_path: Path) -> None:
    y = tmp_path / "g.yaml"
    y.write_text("edition: classic-clue-1996\nseed: 5\nplayers:\n  - {kind: baseline, bot: expert}\n  - {kind: llm, strategy: bayesian}\n  - {kind: baseline}\n")
    res = runner.invoke(app, ["play", "--config", str(y), "--ui", "cli", "--quiet", "--no-tools", "--dice", "2", "--strategy", "strategies/room_rusher.md", "--replay-dir", str(tmp_path)])
    assert res.exit_code == 0, res.output
    rec = json.loads(next(tmp_path.glob("*.jsonl")).read_text().splitlines()[0])
    assert rec["config"]["dice"] == 2
    llm = next(p for p in rec["players"] if p["kind"] == "llm")
    assert llm["tools"] is False and llm["strategy"].endswith("bayesian_probabilist.md")


def test_cli_requires_players_or_config() -> None:
    res = runner.invoke(app, ["play"])
    assert res.exit_code != 0


def test_cli_tournament_flags(tmp_path: Path) -> None:
    rep = tmp_path / "t.csv"
    res = runner.invoke(
        app,
        [
            "tournament",
            "--games",
            "2",
            "--players",
            "llm:bayesian,baseline:expert,baseline",
            "--report",
            str(rep),
            "--tool-mode",
            "native",
            "--prompt-profile",
            "compact",
            "--max-usd",
            "1",
            "--replay-dir",
            str(tmp_path / "r"),
        ],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(rep.with_suffix(".json").read_text())
    assert any("native" in r["agent"] and "compact" in r["agent"] for r in data["table"])
    assert rep.exists() and list((tmp_path / "r").glob("*.jsonl"))


def test_cli_eval_offline(tmp_path: Path) -> None:
    res = runner.invoke(app, ["eval", "--games", "1", "--out", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "report.md").exists() and (tmp_path / "report.json").exists()


def test_cli_live_eval_mock(tmp_path: Path) -> None:
    res = runner.invoke(app, ["live-eval", "--games", "1", "--provider", "mock", "--out", str(tmp_path), "--brackets", "ponder"])
    assert res.exit_code == 0, res.output
    rep = json.loads((tmp_path / "live_report.json").read_text())
    assert set(rep["brackets"]["ponder"]) == {"native", "native+ponder"}


# ------------------------------------------------------------------ config / factory
def test_yaml_aliases_and_defaults(tmp_path: Path) -> None:
    y = tmp_path / "g.yaml"
    y.write_text("edition: modern\nplayers:\n  - {kind: baseline}\n  - {kind: baseline}\n  - {kind: baseline}\n")
    cfg, specs, seed, raw = load_yaml_config(y)
    assert cfg.edition == "modern" and cfg.dice == 2 and seed == 0 and [s.id for s in specs] == ["P1", "P2", "P3"]
    cfg2, *_ = load_yaml_config(Path("game.yaml"))
    assert cfg2.num_players == 4 and cfg2.dice == 2


def test_parse_players_errors_and_labels() -> None:
    with pytest.raises(ValueError):
        parse_players_arg("alien")
    specs = parse_players_arg("llm:aggressive:gpt-x:notools,llm::native,baseline:random")
    assert specs[0].model == "gpt-x" and specs[0].tools is False and specs[0].label().endswith("no-tools")
    assert specs[1].strategy is None and specs[1].tool_mode == "native" and specs[1].label() == "llm:mock:native"
    with pytest.raises(ValueError):
        make_agent(specs[0].model_copy(update={"kind": "ghost"}))


# ------------------------------------------------------------------ eval report
def test_run_eval_offline_files(tmp_path: Path) -> None:
    rep = run_eval(games=1, seed=1, out_dir=str(tmp_path))
    assert rep["live"] is False and len(rep["main"]["table"]) == 4
    assert (tmp_path / "charts.png").exists() or (tmp_path / "charts.txt").exists()


def test_run_live_eval_budget_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from clue.agents import llm_client as LC

    calls = {"n": 0}
    orig = LC.MockLLMClient.complete

    def boom(self, *a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] > 3:
            raise LC.BudgetExceeded("cap")
        return orig(self, *a, **k)

    monkeypatch.setattr(LC.MockLLMClient, "complete", boom)
    rep = run_live_eval("mock", 2, out_dir=str(tmp_path), provider="mock", brackets=("ablation",), verbose=False)
    assert rep["stopped"] and "ablation" in rep["stopped"]
    assert (tmp_path / "live_report.md").exists()


# ------------------------------------------------------------------ human CLI agent
def test_human_cli_agent_scripted_game() -> None:
    """A scripted human: always picks option 0 (first legal action), suggests when offered, and shows first card."""
    specs = parse_players_arg("human,baseline:expert,baseline")
    gm = GameManager.create(specs, seed=8)
    script = iter(["x", "0"] * 10_000)  # one invalid answer, then option 0, repeated
    human = HumanCLIAgent("P1", input_fn=lambda _prompt: next(script))
    agents = {"P1": human, **{s.id: make_agent(s, seed=8) for s in specs[1:]}}
    human.on_event({"type": "game_start"})
    human.on_event({"type": "turn_start", "turn": 0, "player": "P1"})
    run_game(gm, agents)
    s = gm.summary()
    assert s["winner"] is not None and s["illegal_attempts"].get("P1", 0) == 0


def test_describe_event_covers_types() -> None:
    evs = [
        {"type": "roll", "player": "P1", "dice": [3, 4], "total": 7},
        {"type": "move", "player": "P1", "from": "r1c1", "to": "Hall"},
        {"type": "passage", "player": "P1", "from": "Lounge", "to": "Conservatory"},
        {"type": "suggest", "player": "P1", "suspect": "a", "weapon": "b", "room": "c"},
        {"type": "cannot_disprove", "player": "P2"},
        {"type": "can_disprove", "player": "P2"},
        {"type": "disproved", "player": "P2", "suggester": "P1", "card": "Rope"},
        {"type": "disproved", "player": "P2", "suggester": "P1"},
        {"type": "no_one_disproved", "player": "P1"},
        {"type": "accuse", "player": "P1", "suspect": "a", "weapon": "b", "room": "c", "correct": False},
        {"type": "eliminated", "player": "P1"},
        {"type": "game_over", "winner": "P2", "solution": ["a", "b", "c"]},
        {"type": "turn_start", "turn": 3, "player": "P1"},
        {"type": "boxed_in", "player": "P1"},
        {"type": "weird", "player": "P1"},
    ]
    out = [describe_event(e) for e in evs]
    assert all(isinstance(o, str) and o for o in out) and "WRONG" in out[9] and "a card" in out[7]


def test_cli_save_then_resume(tmp_path: Path) -> None:
    """--save checkpoints every action; interrupting and --resume-ing finishes the very same game."""
    from clue.manager import runner as runner_mod

    ref = runner.invoke(app, ["play", "--players", "baseline,baseline:expert,llm:aggressive", "--seed", "21", "--ui", "cli", "--quiet", "--replay-dir", str(tmp_path / "ref")])
    assert ref.exit_code == 0, ref.output
    ref_hash = (tmp_path / "ref" / "game_21.jsonl").read_text()

    # simulate a crash after 7 actions
    orig = runner_mod.run_game
    n = {"k": 0}

    def stopping(gm, agents, on_events=None, **kw):  # type: ignore[no-untyped-def]
        kw["stop"] = lambda: n.__setitem__("k", n["k"] + 1) or n["k"] >= 7
        return orig(gm, agents, on_events, **kw)

    import clue.__main__ as cli

    cli.run_game, saved = stopping, cli.run_game
    try:
        cp = tmp_path / "cp.json"
        r1 = runner.invoke(app, ["play", "--players", "baseline,baseline:expert,llm:aggressive", "--seed", "21", "--ui", "cli", "--quiet", "--save", str(cp), "--replay-dir", str(tmp_path / "part")])
    finally:
        cli.run_game = saved
    assert r1.exit_code == 0, r1.output
    assert cp.exists()
    r2 = runner.invoke(app, ["play", "--resume", str(cp), "--ui", "cli", "--quiet", "--replay-dir", str(tmp_path / "res")])
    assert r2.exit_code == 0, r2.output
    assert "Resumed" in r2.output
    res_hash = (tmp_path / "res" / "game_21.jsonl").read_text()
    assert res_hash == ref_hash
    assert not cp.exists()  # finished -> checkpoint removed
    r3 = runner.invoke(app, ["play", "--resume", str(cp)])
    assert r3.exit_code != 0

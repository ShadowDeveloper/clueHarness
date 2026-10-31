"""Glue coverage: CLI commands (CliRunner), YAML config, eval report, human CLI agent, live-eval runner (mock)."""

from __future__ import annotations

import asyncio
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
def test_cli_generates_seed_when_not_configured_and_preserves_explicit_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import clue.__main__ as cli

    config = tmp_path / "unseeded.yaml"
    config.write_text("players:\n  - {kind: baseline}\n  - {kind: baseline}\n  - {kind: baseline}\n")
    generated = iter((123456, 654321))
    monkeypatch.setattr(cli.secrets, "randbits", lambda _bits: next(generated))

    first = cli._specs(str(config), None, None, None, None, False)[2]
    second = cli._specs(str(config), None, None, None, None, False)[2]
    assert (first, second) == (123456, 654321)
    assert cli._specs(str(config), None, 7, None, None, False)[2] == 7

    config.write_text("seed: 42\nplayers:\n  - {kind: baseline}\n  - {kind: baseline}\n  - {kind: baseline}\n")
    assert cli._specs(str(config), None, None, None, None, False)[2] == 42


def test_yaml_baseline_bot_choices(tmp_path: Path) -> None:
    from clue.agents.baselines import BaselineHeuristicBot, BaselineRandomBot
    from clue.agents.expert import BaselineExpertBot

    config = tmp_path / "bots.yaml"
    config.write_text(
        """players:
  - {kind: baseline, bot: none}
  - {kind: baseline, bot: expert}
  - {kind: baseline, bot: random}
"""
    )
    _, specs, _, _ = load_yaml_config(config)
    agents = [make_agent(spec, seed=7) for spec in specs]

    assert isinstance(agents[0], BaselineHeuristicBot)
    assert isinstance(agents[1], BaselineExpertBot)
    assert isinstance(agents[2], BaselineRandomBot)
    assert specs[0].label() == "baseline:heuristic"
    with pytest.raises(ValueError, match="unknown baseline bot"):
        make_agent(specs[0].model_copy(update={"bot": "typo"}))


def test_yaml_aliases_and_defaults(tmp_path: Path) -> None:
    y = tmp_path / "g.yaml"
    y.write_text("edition: modern\nplayers:\n  - {kind: baseline}\n  - {kind: baseline}\n  - {kind: baseline}\n")
    cfg, specs, seed, raw = load_yaml_config(y)
    assert cfg.edition == "modern" and cfg.dice == 2 and seed == 0 and [s.id for s in specs] == ["P1", "P2", "P3"]
    cfg2, *_ = load_yaml_config(Path("game.yaml"))
    assert cfg2.num_players == 4 and cfg2.dice == 2


def test_strategy_game_yaml_and_spectate(monkeypatch: pytest.MonkeyPatch) -> None:
    """YAML spectate goes through the real run_tui path, not just a mocked UI-selection seam."""
    from clue.tui import app as tui_app

    seen: dict[str, object] = {}

    def fake_app_run(tui: tui_app.ClueApp) -> None:
        seen["app"] = tui
        seen["gm"] = tui.gm
        seen["agents"] = tui.agents

        async def mount_tui() -> None:
            async with tui.run_test(size=(170, 48)) as pilot:
                await pilot.pause()
                seen["status"] = str(tui.query_one("#status").render())
                seen["omniscient"] = bool(tui.query_one("#omni").display)
                tui.exit()

        asyncio.run(mount_tui())

    monkeypatch.setattr(tui_app.ClueApp, "_game_loop", lambda _tui: None)
    monkeypatch.setattr(tui_app.ClueApp, "run", fake_app_run)
    result = runner.invoke(app, ["play", "--config", "strategy_game.yaml"])

    assert result.exit_code == 0, result.output
    gm = seen["gm"]
    assert isinstance(gm, GameManager)
    assert gm.config.edition == "large" and gm.config.num_players == 10
    assert [s.name for s in gm.specs] == ["Probabalist", "Note-taker", "Accuser", "Hunter", "Liar", "Rusher", "Baseline", "Heuristic", "Expert", "Random"]
    llm_specs = [s for s in gm.specs if s.kind == "llm"]
    assert len(llm_specs) == 6 and all(s.model == "openai" and s.temperature is None for s in llm_specs)
    assert [Path(s.strategy or "").stem for s in llm_specs] == ["bayesian_probabilist", "conservative_notebook", "aggressive_accuser", "info_value_hunter", "deceptive_misdirector", "room_rusher"]
    assert [s.bot for s in gm.specs[6:]] == [None, "heuristic", "expert", "random"]
    assert len(seen["agents"]) == 10
    tui = seen["app"]
    assert isinstance(tui, tui_app.ClueApp)
    assert tui.human is None and tui.viewer is None and tui.ponder is True
    assert seen["omniscient"] is True
    assert "Spectating" in str(seen["status"]) and "omniscient" in str(seen["status"])


def test_yaml_player_names_are_used_in_tui_roster(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from clue.manager.game_manager import PlayerSpec
    from clue.tui import app as tui_app

    config = tmp_path / "named_players.yaml"
    config.write_text(
        """spectate: true
players:
  - id: P1
    name: Bayesian
    kind: llm
    model: openai
    strategy: bayesian
  - id: P2
    name: The Conservative
    kind: baseline
  - id: P3
    name: Baseline
    kind: baseline
"""
    )
    seen: dict[str, object] = {}

    def fake_app_run(tui: tui_app.ClueApp) -> None:
        async def mount_tui() -> None:
            async with tui.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                seen["subtitle"] = tui.sub_title
                seen["event"] = tui._describe_event({"type": "turn_start", "turn": 1, "player": "P1"})
                tui.exit()

        asyncio.run(mount_tui())

    monkeypatch.setattr(tui_app.ClueApp, "_game_loop", lambda _tui: None)
    monkeypatch.setattr(tui_app.ClueApp, "run", fake_app_run)
    result = runner.invoke(app, ["play", "--config", str(config)])

    assert result.exit_code == 0, result.output
    assert seen["subtitle"] == "P1: Bayesian  P2: The Conservative  P3: Baseline"
    assert seen["event"] == "--- Turn 1: Bayesian (P1) ---"
    bayesian = PlayerSpec(id="P1", name="AI", kind="llm", model="mock", strategy="bayesian")
    aggressive = PlayerSpec(id="P2", name="AI", kind="llm", model="mock", strategy="aggressive")
    assert bayesian.display_label() == aggressive.display_label() == "AI"
    assert bayesian.label() != aggressive.label()


def test_cli_spectate_flag_still_uses_real_run_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    from clue.tui import app as tui_app

    launched: list[tui_app.ClueApp] = []
    monkeypatch.setattr(tui_app.ClueApp, "run", lambda tui: launched.append(tui))
    result = runner.invoke(app, ["play", "--players", "baseline,baseline,baseline", "--spectate", "--no-autosave"])

    assert result.exit_code == 0, result.output
    assert len(launched) == 1 and launched[0].human is None and launched[0].viewer is None


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

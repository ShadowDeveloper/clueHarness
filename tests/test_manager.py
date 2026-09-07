"""Manager tests: privacy (no leakage), replay determinism, save/load, notebook derivation, runner fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from clue.agents.base import PlayerAgent
from clue.agents.baselines import BaselineHeuristicBot, BaselineRandomBot
from clue.agents.llm_agent import LLMPlayerAgent
from clue.agents.llm_client import MockLLMClient, extract_json
from clue.manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.rules import Action
from clue.tools import can_accuse_confidently, get_possible_solutions, solution_probabilities, suggestion_ev

SPECS = [PlayerSpec(id=f"P{i}", kind="baseline", bot="heuristic") for i in range(1, 5)]


def play(seed: int, bots: str = "hhrr") -> GameManager:
    gm = GameManager.create(SPECS, seed=seed)
    agents: dict[str, PlayerAgent] = {}
    for i, (pid, b) in enumerate(zip(gm.player_ids(), bots, strict=True)):
        agents[pid] = BaselineHeuristicBot(pid, seed + i) if b == "h" else BaselineRandomBot(pid, seed + i)
    return run_game(gm, agents)


# ---------------- privacy ----------------


def test_no_leak_in_redacted_replay() -> None:
    gm = play(11)
    full = gm.export_replay(None)
    shown = [r for r in full if r.get("type") == "disproved"]
    assert shown, "game had no disproofs?"
    for viewer in gm.player_ids():
        red = gm.export_replay(viewer)
        assert not any("solution" in r for r in red if r.get("type") == "game_start")
        for r in red:
            if r.get("type") == "disproved":
                involved = viewer in (r["suggester"], r["disprover"])
                assert ("card" in r) == involved, (viewer, r)
            if r.get("type") == "game_start":
                assert "hands" not in r
            if r["kind"] == "action" and r["type"] == "show_card":
                assert ("card" in r) == (viewer == r["player"] or viewer in [x["suggester"] for x in full if x.get("seq") == r["seq"] + 1])
            if r["kind"] in ("tool_call", "agent_note"):
                assert r["player"] == viewer


def test_observation_hides_other_hands_and_solution() -> None:
    gm = play(12)
    for pid in gm.player_ids():
        obs = gm.get_observation(pid)
        assert obs["you"]["hand"] == gm.state.player(pid).hand
        for q in obs["board"]["players"]:
            assert "hand" not in q  # only hand_size
        for e in obs["public_history"]:
            if e["type"] == "disproved":
                assert ("card" in e) == (pid in (e["suggester"], e["disprover"]))
        assert "solution" not in obs and "solution" not in json.dumps(obs["notebook"])
        # the notebook never claims to know a solution card's holder
        for c in gm.state.solution:
            assert c not in gm.notebooks[pid].known_holder


def test_notebook_facts_are_sound() -> None:
    """Every derived fact must be true w.r.t. the hidden state."""
    for seed in range(5):
        gm = play(100 + seed)
        hands = {p.id: set(p.hand) for p in gm.state.players}
        for nb in gm.notebooks.values():
            for card, holder in nb.known_holder.items():
                assert card in hands[holder]
            for p, cards in nb.not_held.items():
                assert not (set(cards) & hands[p])
            for c in nb.has_one_of:
                assert set(c.cards) & hands[c.player]
            sols = get_possible_solutions(nb, gm.player_ids(), {p: len(h) for p, h in hands.items()})
            assert tuple(gm.state.solution) in sols


# ---------------- determinism ----------------


def test_same_seed_same_replay_hash() -> None:
    a, b = play(21), play(21)
    assert a.replay_hash() == b.replay_hash()
    assert a.export_replay(None) == b.export_replay(None)


def test_different_seed_different_deal() -> None:
    a, b = GameManager.create(SPECS, seed=1), GameManager.create(SPECS, seed=2)
    assert a.state.solution != b.state.solution or a.state.players[0].hand != b.state.players[0].hand


def test_replay_files_written(tmp_path: Path) -> None:
    gm = play(31)
    p = gm.write_replay(tmp_path / "g.jsonl")
    lines = p.read_text().splitlines()
    assert len(lines) == len(gm.log)
    r = gm.write_replay(tmp_path / "g_P2.json", viewer="P2")
    data = json.loads(r.read_text())
    assert all("hands" not in d for d in data)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    gm = GameManager.create(SPECS, seed=5)
    agents = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    # play a few actions
    for _ in range(12):
        if gm.finished:
            break
        pid = gm.acting_player()
        obs = gm.get_observation(pid)
        obs["_notebook_obj"] = gm.notebooks[pid]
        acts = gm.legal_actions(pid, include_accusations=False)
        if gm.state.phase == "disprove":
            a = Action(type="show_card", player=pid, card=agents[pid].choose_card_to_show(obs, [x.card for x in acts if x.card]))
        else:
            a = agents[pid].choose_action(obs, acts)
        gm.step(a)
    gm.save(tmp_path / "save.json")
    gm2 = GameManager.load(tmp_path / "save.json")
    assert gm2.state == gm.state and gm2.replay_hash() == gm.replay_hash()
    assert gm2.notebooks["P1"].model_dump() == gm.notebooks["P1"].model_dump()
    # continuing both (with identically-seeded fresh agents) yields identical futures
    run_game(gm, {pid: BaselineHeuristicBot(pid, 99 + i) for i, pid in enumerate(gm.player_ids())})
    run_game(gm2, {pid: BaselineHeuristicBot(pid, 99 + i) for i, pid in enumerate(gm2.player_ids())})
    assert gm.winner == gm2.winner and gm.replay_hash() == gm2.replay_hash()


# ---------------- runner: illegal action handling ----------------


class BadBot(PlayerAgent):
    kind = "baseline"

    def __init__(self, pid: str) -> None:
        super().__init__(pid)
        self.calls = 0

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        self.calls += 1
        return Action(type="move", player=self.id, to="Kitchen")  # almost always illegal

    def choose_card_to_show(self, observation: dict[str, Any], cards: list[str]) -> str:
        return "Banana"


def test_runner_rejects_illegal_and_falls_back() -> None:
    gm = GameManager.create(SPECS, seed=3)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    bad = BadBot("P1")
    agents["P1"] = bad
    run_game(gm, agents)
    assert gm.finished
    notes = [r for r in gm.export_replay("P1") if r["kind"] == "agent_note"]
    assert any(n["summary"] == "illegal_action" for n in notes)
    assert any(n["summary"] == "fallback_action" for n in notes)
    assert gm.illegal_attempts["P1"] >= 2
    # every applied action was legal: the rules engine would have raised otherwise
    assert all(r["kind"] != "action" or r["player"] in gm.player_ids() for r in gm.export_replay(None))


# ---------------- LLM agent with mock ----------------


def test_llm_agent_mock_plays_and_logs_tools() -> None:
    gm = GameManager.create(SPECS, seed=8)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    agents["P1"] = LLMPlayerAgent("P1", client=MockLLMClient(), strategy_path="strategies/bayesian_probabilist.md")
    run_game(gm, agents)
    rep = gm.export_replay("P1")
    assert any(r["kind"] == "tool_call" and r["tool"] == "solution_probabilities" for r in rep)
    assert any(r["kind"] == "agent_note" and r["summary"] == "llm_response" for r in rep)
    assert gm.illegal_attempts.get("P1", 0) == 0


def test_llm_agent_retry_then_fallback() -> None:
    gm = GameManager.create(SPECS, seed=9)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    garbage = MockLLMClient(policy=lambda s, m: "not json at all")
    llm = LLMPlayerAgent("P1", client=garbage)
    agents["P1"] = llm
    run_game(gm, agents)
    assert llm.stats["fallbacks"] > 0 and llm.stats["retries"] > 0
    rep = gm.export_replay("P1")
    assert any(r["summary"] == "fallback_to_heuristic" for r in rep if r["kind"] == "agent_note")
    assert gm.illegal_attempts.get("P1", 0) == 0  # fallback always legal


def test_llm_agent_fail_first_then_valid() -> None:
    gm = GameManager.create(SPECS, seed=10)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    llm = LLMPlayerAgent("P1", client=MockLLMClient(fail_first=True))
    agents["P1"] = llm
    run_game(gm, agents)
    assert llm.stats["retries"] == 1 and llm.stats["fallbacks"] == 0


def test_strategy_prompt_is_appended_not_replacing_base() -> None:
    a = LLMPlayerAgent("P1", client=MockLLMClient(), strategy_path="strategies/room_rusher.md")
    b = LLMPlayerAgent("P1", client=MockLLMClient())
    assert a.system_prompt.startswith(b.system_prompt)
    assert "Room Rusher" in a.system_prompt and "Room Rusher" not in b.system_prompt


def test_extract_json_variants() -> None:
    assert extract_json('```json\n{"a": 1}\n```')["a"] == 1
    assert extract_json('Sure! {"action": {"type": "roll"}} hope that helps')["action"]["type"] == "roll"


# ---------------- tools ----------------


def test_tools_shape() -> None:
    gm = play(41)
    nb = gm.notebooks["P1"]
    players = gm.player_ids()
    post = solution_probabilities(nb, players)
    assert abs(sum(v for v in post["cards"].values()) - 3.0) < 1e-6 or post["n_possible"] == 0
    ev = suggestion_ev(nb, players, "P1", "Prof. Plum", "Rope", "Hall")
    assert 0 <= ev["score"] <= 1
    v = can_accuse_confidently(nb, players, 0.5)
    assert "confidence" in v


# ---------------- save / resume with agent memory ----------------


def _mk_agents(gm: GameManager) -> dict:  # type: ignore[type-arg]
    from clue.agents.factory import make_agent

    return {s.id: make_agent(s, seed=gm.seed + i) for i, s in enumerate(gm.specs)}


@pytest.mark.parametrize("players", ["baseline,baseline:expert,llm:aggressive", "baseline:random,baseline:expert,baseline:expert,llm:conservative_notebook:notools"])
def test_resume_reproduces_uninterrupted_game(tmp_path: Path, players: str) -> None:
    """Stop after N actions, save (with agent state), rebuild fresh agents, restore, continue: identical replay hash."""
    from clue.agents.factory import parse_players_arg

    specs = parse_players_arg(players)
    ref = GameManager.create(specs, seed=11)
    run_game(ref, _mk_agents(ref))

    gm = GameManager.create(specs, seed=11)
    agents = _mk_agents(gm)
    n = {"k": 0}
    cut = 9
    run_game(gm, agents, autosave=tmp_path / "cp.json", stop=lambda: n.__setitem__("k", n["k"] + 1) or n["k"] >= cut)  # type: ignore[func-returns-value]
    assert not gm.finished and (tmp_path / "cp.json").exists()

    gm2 = GameManager.load(tmp_path / "cp.json")
    fresh = _mk_agents(gm2)
    restored = gm2.restore_agents(fresh)
    assert set(restored) == set(gm2.player_ids())
    assert gm2.illegal_attempts == gm.illegal_attempts
    run_game(gm2, fresh, autosave=tmp_path / "cp.json")
    assert gm2.finished and gm2.replay_hash() == ref.replay_hash() and gm2.winner == ref.winner
    assert not (tmp_path / "cp.json").exists()  # checkpoint removed once the game finished


def test_agent_state_export_import_roundtrip() -> None:
    from clue.agents.factory import parse_players_arg

    specs = parse_players_arg("baseline,baseline:expert,llm:aggressive")
    gm = GameManager.create(specs, seed=2)
    agents = _mk_agents(gm)
    k = {"n": 0}
    run_game(gm, agents, stop=lambda: k.__setitem__("n", k["n"] + 1) or k["n"] >= 6)  # type: ignore[func-returns-value]
    for pid, ag in agents.items():
        st = ag.export_state()
        json.dumps(st)  # must be JSON-serialisable
        clone = _mk_agents(gm)[pid]
        clone.import_state(st)
        assert clone.export_state() == st

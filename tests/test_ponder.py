"""Parallel-thinking (ponder) tests: interrupts, isolation, merging, non-blocking grace, privacy, determinism."""

from __future__ import annotations

import threading
import time
from typing import Any

from clue.agents.base import PlayerAgent, PonderContext, PonderInterrupted
from clue.agents.baselines import BaselineHeuristicBot
from clue.agents.llm_agent import LLMPlayerAgent
from clue.agents.llm_client import MockLLMClient
from clue.manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.rules import Action

SPECS = [PlayerSpec(id=f"P{i}", kind="baseline") for i in range(1, 5)]


class SlowThinker(BaselineHeuristicBot):
    """Heuristic bot that 'thinks' forever until interrupted, recording how it was stopped."""

    def __init__(self, pid: str, seed: int = 0, block_forever: bool = False) -> None:
        super().__init__(pid, seed)
        self.stops: list[str] = []
        self.started = 0
        self.block_forever = block_forever
        self.saw_snapshot_mutation = False

    def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
        self.started += 1
        nb = observation["_notebook_obj"]
        nb.notes.append("scratch")  # mutating the snapshot must not leak into the real notebook
        ctx.note(f"pondered@{observation['turn']['number']}")
        try:
            if self.block_forever:
                time.sleep(10)  # ignores the interrupt: exercises the grace timeout path
                return {"slept": True}
            while True:
                ctx.tool("get_unseen_cards")
                ctx.wait(0.01)
        except PonderInterrupted as e:
            self.stops.append(str(e))
            raise


def test_ponder_sessions_are_interrupted_by_info_and_turn() -> None:
    gm = GameManager.create(SPECS, seed=3)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    slow = SlowThinker("P2", 1)
    agents["P2"] = slow
    run_game(gm, agents, ponder=True, ponder_grace=1.0)
    assert gm.finished
    assert slow.started > 0
    assert "new_information" in slow.stops and "your_turn" in slow.stops
    st = gm.ponder_stats["P2"]
    assert st["interrupted_by_info"] > 0 and st["interrupted_by_turn"] > 0
    assert st.get("grace_timeouts", 0) == 0
    # snapshot isolation: "scratch" never reached the real notebook, but ctx notes did
    assert "scratch" not in gm.notebooks["P2"].notes
    assert any(n.startswith("pondered@") for n in gm.notebooks["P2"].notes)


def test_grace_timeout_does_not_block_game() -> None:
    gm = GameManager.create(SPECS, seed=4)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    agents["P3"] = SlowThinker("P3", 2, block_forever=True)
    t0 = time.monotonic()
    run_game(gm, agents, ponder=True, ponder_grace=0.05)
    assert gm.finished
    assert gm.ponder_stats["P3"]["grace_timeouts"] >= 1
    # a 10 s sleeper per session would take minutes if we waited; the game must finish quickly
    assert time.monotonic() - t0 < 60
    # orphaned sleepers are daemon threads; at most one per timed-out session
    assert threading.active_count() <= gm.ponder_stats["P3"]["sessions"] + 10


def test_ponder_records_are_private_and_logged() -> None:
    gm = GameManager.create(SPECS, seed=5)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    run_game(gm, agents, ponder=True)
    full = gm.export_replay(None)
    assert any(r["kind"] == "ponder" for r in full)
    assert any(r["kind"] == "tool_call" and r["args"].get("during") == "ponder" for r in full)
    for viewer in gm.player_ids():
        for r in gm.export_replay(viewer):
            if r["kind"] in ("ponder", "tool_call"):
                assert r["player"] == viewer


def test_game_outcome_identical_with_and_without_ponder_for_heuristics() -> None:
    """Heuristic pondering only caches/annotates; it must not change decisions, so replays of *events* match."""

    def play(ponder: bool) -> list[dict[str, Any]]:
        gm = GameManager.create(SPECS, seed=6)
        agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
        run_game(gm, agents, ponder=ponder)
        return [r for r in gm.export_replay(None) if r["kind"] in ("event", "action")]

    a, b = play(False), play(True)
    strip = lambda rs: [{k: v for k, v in r.items() if k != "seq"} for r in rs]  # noqa: E731
    assert strip(a) == strip(b)


def test_llm_agent_ponders_with_mock_and_carries_plan() -> None:
    gm = GameManager.create(SPECS, seed=8)
    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    llm = LLMPlayerAgent("P1", client=MockLLMClient(), strategy_path="strategies/bayesian_probabilist.md")
    agents["P1"] = llm
    run_game(gm, agents, ponder=True)
    assert llm.stats["ponder_rounds"] > 0
    assert llm.last_plan is not None
    assert any("combos remain" in n for n in gm.notebooks["P1"].notes)
    ponders = [r for r in gm.export_replay("P1") if r["kind"] == "ponder"]
    assert ponders and any(r["result"] and r["result"].get("plan") for r in ponders)
    assert gm.illegal_attempts.get("P1", 0) == 0


def test_ponder_tools_use_snapshot_not_live_state() -> None:
    """Even if the live notebook changes mid-session, the snapshot answers stay consistent."""
    gm = GameManager.create(SPECS, seed=9)
    seen: list[int] = []

    class Probe(BaselineHeuristicBot):
        supports_ponder = True

        def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
            first = len(ctx.tool("get_possible_solutions"))
            time.sleep(0.02)  # deliberately NOT interruptible: let the live game move on underneath us
            second = len(observation["_notebook_obj"].known_holder) and len(ctx._tool_fn("get_possible_solutions"))
            seen.append(first - second)
            return {}

    agents: dict[str, PlayerAgent] = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    agents["P4"] = Probe("P4", 3)
    run_game(gm, agents, ponder=True)
    assert seen and all(d == 0 for d in seen)


def test_ponder_context_api() -> None:
    ctx = PonderContext("P1", lambda name, **a: {"name": name, **a})
    assert ctx.tool("x", k=1) == {"name": "x", "k": 1} and ctx.tool_calls == 1
    ctx.note("a")
    ctx.request_stop("your_turn")
    ctx.request_stop("new_information")  # first reason wins
    assert ctx.reason == "your_turn" and ctx.stopped
    try:
        ctx.check()
        raise AssertionError("expected interrupt")
    except PonderInterrupted as e:
        assert str(e) == "your_turn"
    try:
        ctx.tool("x")
        raise AssertionError("tools must refuse after stop")
    except PonderInterrupted:
        pass
    assert Action(type="roll", player="P1").key() == "roll"

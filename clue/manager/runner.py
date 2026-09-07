"""Drives a GameManager to completion using PlayerAgents. Validates every agent action."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from clue.agents.base import PlayerAgent
from clue.manager.game_manager import GameManager
from clue.manager.ponder import PonderManager
from clue.rules import Action, IllegalAction, is_legal

Callback = Callable[[GameManager, list[dict[str, Any]]], None]


def _fallback(gm: GameManager, pid: str) -> Action:
    acts = gm.legal_actions(pid, include_accusations=False)
    pref = ["end_turn", "roll", "move", "show_card", "passage"]
    for t in pref:
        for a in acts:
            if a.type == t:
                return a
    return acts[0]


class GameInterrupted(Exception):
    """Raised by an agent (e.g. a UI-backed human) to abort the current decision; the game is left resumable."""


def run_game(
    gm: GameManager,
    agents: dict[str, PlayerAgent],
    on_events: Callback | None = None,
    max_illegal_per_player: int = 3,
    ponder: bool = False,
    ponder_grace: float = 2.0,
    autosave: str | Path | None = None,
    stop: Callable[[], bool] | None = None,
) -> GameManager:
    """Loop until finished. Illegal actions are rejected, logged, retried once, then replaced by a safe fallback.

    `autosave`: checkpoint file rewritten after every action (atomic) - `clue play --resume FILE` continues from it.
    `stop`: polled after every action; when it returns True the loop exits early (game left unfinished, resumable).

    With `ponder=True`, idle agents that declare `supports_ponder` think in background threads between their
    turns (see clue/manager/ponder.py); they are interrupted on new information and before their own decision.
    """
    pm = PonderManager(gm, agents, grace=ponder_grace) if ponder else None
    if pm:
        gm._ponder_manager = pm  # exposed for UIs (read-only)
        pm.start_idle(gm.acting_player(), trigger="game_start")
    while not gm.finished:
        if stop and stop():
            break
        pid = gm.acting_player()
        agent = agents[pid]
        ponder_summary = pm.before_decision(pid) if pm else None
        obs = gm.get_observation(pid)
        obs["_notebook_obj"] = gm.notebooks[pid]  # object handle for symbolic tools (not serialised)
        obs["_manager"] = gm
        if ponder_summary:
            obs["ponder_summary"] = {k: v for k, v in ponder_summary.items() if k in ("result", "notes", "stopped_by", "pending")}
        acts = gm.legal_actions(pid, include_accusations=False)
        action: Action | None = None
        interrupted = False
        for attempt in range(2):
            try:
                if gm.state.phase == "disprove":
                    cards = [a.card for a in acts if a.card]
                    card = agent.choose_card_to_show(obs, cards)
                    cand = Action(type="show_card", player=pid, card=card)
                else:
                    cand = agent.choose_action(obs, acts)
                if cand.player != pid:
                    raise IllegalAction(f"action for wrong player {cand.player}")
                if not is_legal(gm.state, cand):
                    raise IllegalAction(f"{cand.key()} not legal")
                action = cand
                break
            except GameInterrupted:
                interrupted = True
                break
            except (IllegalAction, ValueError, KeyError, IndexError) as e:
                gm.illegal_attempts[pid] = gm.illegal_attempts.get(pid, 0) + 1
                gm.log_agent_note(pid, {"summary": "illegal_action", "attempt": attempt, "error": str(e)})
                obs["last_error"] = str(e)
        if interrupted:
            break  # nothing applied this iteration: state + checkpoint are consistent
        if action is None:
            action = _fallback(gm, pid)
            gm.log_agent_note(pid, {"summary": "fallback_action", "action": action.model_dump(exclude_none=True)})
        events = gm.step(action)
        evs = [e.redacted_for(None) for e in events]
        for ag_id, ag in agents.items():
            for ev in events:
                ag.on_event(ev.redacted_for(ag_id))
        if pm and not gm.finished:
            pm.on_events(evs, gm.acting_player())
        if on_events:
            on_events(gm, evs)
        if autosave and not gm.finished:
            if pm:
                gm.ponder_stats = pm.stats
            gm.save(autosave, agents)
        if stop and stop() and not gm.finished:
            break
    if pm:
        pm.shutdown()
        gm.ponder_stats = pm.stats
    if autosave and gm.finished:
        Path(autosave).unlink(missing_ok=True)  # finished games live in the replay, not the checkpoint
    return gm

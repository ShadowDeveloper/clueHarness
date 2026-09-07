"""PonderManager: lets idle agents think in parallel while others act (like UCI "ponder").

Lifecycle per idle player:
  start  -> a daemon thread calls agent.ponder(snapshot_observation, ctx)
  event  -> if the event is informative for that player, ctx.request_stop("new_information");
            the session is finalised and a fresh one started on the new observation
  turn   -> ctx.request_stop("your_turn"); the runner waits up to `grace` seconds for the thread to
            return, merges its notes, and only then asks the agent for its real action
  end    -> notes are merged into the real notebook and a private `ponder` LogRecord is written

Agents only ever see a deep-copied observation and a *snapshot* notebook, so a pondering thread can never
race the live game state. Late-finishing sessions (e.g. an LLM call that outlives the grace period) are
merged when they land — the game never blocks on them.
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from clue.agents.base import PlayerAgent, PonderContext, PonderInterrupted
from clue.manager.notebook import Notebook

if TYPE_CHECKING:
    from clue.manager.game_manager import GameManager

# events that change what an idle player knows -> restart their pondering
INFORMATIVE = {"suggest", "cannot_disprove", "disproved", "no_one_disproved", "accuse", "eliminated", "game_over"}


@dataclass
class Session:
    player: str
    ctx: PonderContext
    thread: threading.Thread
    started: float
    trigger: str
    result: dict[str, Any] | None = None
    error: str | None = None
    finalised: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class PonderManager:
    def __init__(self, gm: GameManager, agents: dict[str, PlayerAgent], grace: float = 2.0, min_restart_interval: float = 0.05) -> None:
        self.gm = gm
        self.agents = agents
        self.grace = grace
        self.min_restart_interval = min_restart_interval
        self.sessions: dict[str, Session] = {}
        self.stats: dict[str, dict[str, int]] = {}
        self._done_on_current_info: set[str] = set()
        self._orphans: list[Session] = []  # superseded / timed-out sessions still running
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public API
    def eligible(self, pid: str) -> bool:
        ag = self.agents.get(pid)
        return bool(ag and ag.supports_ponder) and not self.gm.state.player(pid).eliminated and not self.gm.finished

    def start_idle(self, acting: str, trigger: str = "step", only_new_info: bool = False) -> None:
        """Ensure every eligible non-acting player has a running session.

        A player who already finished a session on the current information does not restart until
        something informative happens (`only_new_info`), so idle bots don't spin on every dice roll.
        """
        for pid in self.gm.player_ids():
            if pid == acting or not self.eligible(pid):
                continue
            s = self.sessions.get(pid)
            if s and s.thread.is_alive() and not s.ctx.stopped:
                continue
            if only_new_info and pid in self._done_on_current_info:
                continue
            self._done_on_current_info.discard(pid)
            self._start(pid, trigger)

    def on_events(self, events: list[dict[str, Any]], acting_next: str) -> None:
        """Called after every applied action. Interrupts sessions invalidated by new information."""
        types = {e["type"] for e in events}
        informative = bool(types & INFORMATIVE)
        if informative:
            self._done_on_current_info.clear()
        for pid, s in list(self.sessions.items()):
            if pid == acting_next:
                continue
            if informative and s.thread.is_alive() and not s.ctx.stopped:
                s.ctx.request_stop("new_information")
        self._reap()
        self.start_idle(acting_next, trigger="new_information" if informative else "step", only_new_info=True)

    def before_decision(self, pid: str) -> dict[str, Any] | None:
        """Player `pid` is about to act: stop their pondering, wait (bounded), merge, return summary."""
        s = self.sessions.get(pid)
        if s is None:
            return None
        s.ctx.request_stop("your_turn")
        s.thread.join(self.grace)
        if s.thread.is_alive():
            self._bump(pid, "grace_timeouts")
            # leave it running as an orphan; it is merged when it lands (see _reap)
            with self._lock:
                self._orphans.append(s)
                if self.sessions.get(pid) is s:
                    del self.sessions[pid]
            return {"pending": True}
        return self._finalise(s)

    def shutdown(self) -> None:
        for s in list(self.sessions.values()) + list(self._orphans):
            s.ctx.request_stop("game_over")
        for s in list(self.sessions.values()) + list(self._orphans):
            s.thread.join(self.grace)
        self._reap(include_active=True)

    def _reap(self, include_active: bool = False) -> None:
        """Finalise every session whose thread has exited (non-blocking)."""
        with self._lock:
            candidates = list(self._orphans) + (list(self.sessions.values()) if include_active else [s for s in self.sessions.values() if not s.thread.is_alive()])
        for s in candidates:
            if not s.thread.is_alive():
                self._finalise(s)
                with self._lock:
                    if s in self._orphans:
                        self._orphans.remove(s)

    # ------------------------------------------------------------------ internals
    def _start(self, pid: str, trigger: str) -> None:
        obs = copy.deepcopy(self.gm.get_observation(pid))
        snapshot = Notebook(**self.gm.notebooks[pid].model_dump())
        obs["_notebook_obj"] = snapshot  # tools work on the snapshot only
        obs["_ponder"] = True
        agent = self.agents[pid]

        def tool_fn(name: str, **args: Any) -> Any:
            res = _run_tool(obs, pid, name, args)
            self.gm.log_tool_call(pid, name, {**args, "during": "ponder"}, res)
            return res

        ctx = PonderContext(pid, tool_fn)
        session = Session(player=pid, ctx=ctx, thread=threading.Thread(daemon=True), started=time.monotonic(), trigger=trigger)

        def run() -> None:
            try:
                session.result = agent.ponder(obs, ctx) or {}
            except PonderInterrupted:
                session.result = {"interrupted": ctx.reason}
            except Exception as e:  # never let a pondering bug kill the game
                session.error = f"{type(e).__name__}: {e}"

        session.thread = threading.Thread(target=run, name=f"ponder-{pid}", daemon=True)
        old = self.sessions.get(pid)
        if old:
            if old.thread.is_alive():
                old.ctx.request_stop("superseded")
                with self._lock:
                    self._orphans.append(old)
            else:
                self._finalise(old)
        self.sessions[pid] = session
        self._bump(pid, "sessions")
        session.thread.start()

    def _finalise(self, s: Session) -> dict[str, Any]:
        with s.lock:
            if s.finalised:
                return s.result or {}
            s.finalised = True
        nb = self.gm.notebooks[s.player]
        new_notes = [n for n in dict.fromkeys(s.ctx.notes) if n not in nb.notes]
        nb.notes.extend(new_notes)
        if s.ctx.reason not in ("new_information", "superseded") and self.sessions.get(s.player) is s:
            self._done_on_current_info.add(s.player)
        summary = {
            "trigger": s.trigger,
            "stopped_by": s.ctx.reason,
            "duration_ms": int((time.monotonic() - s.started) * 1000),
            "tool_calls": s.ctx.tool_calls,
            "rounds": s.ctx.rounds,
            "notes": new_notes,
            "result": s.result,
            "error": s.error,
        }
        self.gm.log_ponder(s.player, summary)
        self._bump(s.player, "tool_calls", s.ctx.tool_calls)
        self._bump(s.player, "notes", len(s.ctx.notes))
        if s.ctx.reason == "new_information":
            self._bump(s.player, "interrupted_by_info")
        elif s.ctx.reason == "your_turn":
            self._bump(s.player, "interrupted_by_turn")
        if s.error:
            self._bump(s.player, "errors")
        if self.sessions.get(s.player) is s:
            del self.sessions[s.player]
        return summary

    def _bump(self, pid: str, key: str, n: int = 1) -> None:
        self.stats.setdefault(pid, {})[key] = self.stats.setdefault(pid, {}).get(key, 0) + n


def _run_tool(obs: dict[str, Any], pid: str, name: str, args: dict[str, Any]) -> Any:
    """Dispatch a symbolic tool against the snapshot notebook carried in `obs`."""
    from clue.tools import (
        can_accuse_confidently,
        get_possible_solutions,
        get_unseen_cards,
        hard_deductions,
        holder_probabilities,
        opponent_threat,
        solution_probabilities,
        suggestion_ev,
        update_notebook,
    )

    nb: Notebook = obs["_notebook_obj"]
    players = [p["id"] for p in obs["board"]["players"]]
    sizes = {p["id"]: p["hand_size"] for p in obs["board"]["players"]}
    edition = obs["config"]["edition"]
    if name == "get_unseen_cards":
        return get_unseen_cards(nb, edition)
    if name == "get_possible_solutions":
        return [list(c) for c in get_possible_solutions(nb, players, sizes, edition)]
    if name == "solution_probabilities":
        return solution_probabilities(nb, players, sizes, edition)
    if name == "suggestion_ev":
        return suggestion_ev(nb, players, pid, args["suspect"], args["weapon"], args["room"], edition)
    if name == "can_accuse_confidently":
        return can_accuse_confidently(nb, players, float(args.get("threshold", 0.9)), sizes, edition)
    if name == "update_notebook":
        return update_notebook(nb, str(args["note"]))
    if name == "holder_probabilities":
        return holder_probabilities(nb, players, sizes, edition)
    if name == "hard_deductions":
        return hard_deductions(nb, players, sizes, edition)
    if name == "opponent_threat":
        elim = {p["id"] for p in obs["board"]["players"] if p.get("eliminated")}
        return opponent_threat(nb, players, pid, sizes, edition, obs.get("public_history", []), elim)
    raise KeyError(name)

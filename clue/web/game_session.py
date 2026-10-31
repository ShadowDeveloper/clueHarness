"""One running game: manager + agents + runner thread, human requests, viewer-redacted frames, fan-out to subscribers.

Privacy invariant: `render_frame()` / `render_events()` are the ONLY functions that build data leaving the server for a
game, and both take the *viewer* (derived from the link token by the route layer, never from the client payload).
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Any

from clue.agents.base import PlayerAgent
from clue.agents.human import describe_event
from clue.manager.game_manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.rules import Action, IllegalAction, is_legal
from clue.rules.cards import rooms, suspects, weapons
from clue.tools.coach import coach_hints
from clue.web.human_agent import PendingRequest, WebHumanAgent

OMNI = "__omni__"  # viewer id meaning "omniscient spectator"
TABLE = "__table__"  # viewer id meaning "bystander at the table" (public info only)

Subscriber = Any  # callable(frame: dict) -> None, invoked from the game thread; must be non-blocking


class GameSession:
    def __init__(
        self,
        sid: str,
        gm: GameManager,
        agents: dict[str, PlayerAgent],
        *,
        delay: float = 0.6,
        ponder: bool = False,
        ponder_grace: float = 2.0,
        autosave: str | None = None,
        replay_dir: Path | None = None,
        hotseat: bool = False,
        remote: bool = False,
    ) -> None:
        self.id = sid
        self.gm = gm
        self.agents = agents
        self.delay = delay
        self.ponder = ponder
        self.ponder_grace = ponder_grace
        self.autosave = autosave
        self.replay_dir = replay_dir
        self.hotseat = hotseat
        self.remote = remote  # each human seat has its own link; the game waits in the lobby until all have joined
        self.created = time.time()
        self.paused = False
        self.stopping = False
        self.error: str | None = None
        self.summary: dict[str, Any] | None = None
        self.replay_paths: list[str] = []
        self.pending: PendingRequest | None = None
        self.humans = [pid for pid, a in agents.items() if isinstance(a, WebHumanAgent)]
        # hot-seat: which human seat currently "holds the device"; frames for other human seats are withheld
        self.active_seat: str | None = self.humans[0] if self.humans else None
        self.handoff_pending: str | None = None  # seat that must acknowledge before its private data is sent
        self.coach_used: dict[str, int] = {}
        self.presence: dict[str, int] = {pid: 0 for pid in self.humans}  # human seat -> open sockets
        self.joined: set[str] = set()  # human seats that connected at least once
        self.started = threading.Event()  # remote games wait here until every seat joined (or the host forces start)
        self._lock = threading.RLock()
        self._subs: dict[int, tuple[str, Subscriber]] = {}  # sub id -> (viewer, callback)
        self._sub_seq = 0
        self.idle_since: float | None = time.time()  # None while at least one subscriber is connected
        self._log_cache: list[dict[str, Any]] = []  # all events unredacted + seq (rendered per viewer on demand)
        for pid in self.humans:
            ag = agents[pid]
            assert isinstance(ag, WebHumanAgent)
            ag.on_request = self._on_request
        self.thread = threading.Thread(target=self._run, name=f"game-{sid}", daemon=True)

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        if self.remote and self.waiting_for():
            while not self.started.wait(0.2):
                if self.stopping:
                    self._broadcast(lambda v: {"type": "stopped", "resumable": self.autosave})
                    return
        self.started.set()
        try:
            run_game(
                self.gm,
                self.agents,
                self._on_events,
                ponder=self.ponder,
                ponder_grace=self.ponder_grace,
                autosave=self.autosave,
                stop=lambda: self.stopping,
            )
        except Exception as e:  # keep the session inspectable
            self.error = msg = str(e)
            self._broadcast(lambda v: {"type": "error", "message": msg})
        if self.gm.finished:
            self.summary = self.gm.summary()
            if self.replay_dir:
                self.replay_dir.mkdir(parents=True, exist_ok=True)
                p = self.gm.write_replay(self.replay_dir / f"game_{self.gm.seed}.jsonl")
                self.replay_paths.append(str(p))
                for pid in self.gm.player_ids():
                    self.replay_paths.append(str(self.gm.write_replay(self.replay_dir / f"game_{self.gm.seed}_redacted_{pid}.json", viewer=pid)))
            self._broadcast(lambda v: {"type": "finished", **self.render_finished(v)})
        else:
            self._broadcast(lambda v: {"type": "stopped", "resumable": self.autosave})

    def stop(self, save: bool = True) -> str | None:
        """Ask the loop to end at the next safe point; unblock a pending human; optionally checkpoint first."""
        path: str | None = None
        with self._lock:
            self.stopping = True
            self.paused = False
            if save and not self.gm.finished:
                path = self.autosave or f"saves/game_{self.gm.seed}.json"
                self.gm.save(path, self.agents)
                self.autosave = path
            if self.pending is not None:
                req, self.pending = self.pending, None
                req.reply.put(None)
        return path

    def save(self, path: str | None = None) -> str:
        with self._lock:
            p = path or self.autosave or f"saves/game_{self.gm.seed}.json"
            out = self.gm.save(p, self.agents)
            return str(out)

    # ------------------------------------------------------------------ runner callbacks (game thread)
    def _on_events(self, gm: GameManager, evs: list[dict[str, Any]]) -> None:
        self._broadcast(lambda v: {"type": "events", "events": self.render_events(v, since=len(self.gm.events) - len(evs)), "state": self.render_state(v, light=True)})
        acting = gm.acting_player() if not gm.finished else None
        if acting not in self.humans:
            while self.paused and not self.stopping:
                time.sleep(0.05)
            if self.delay:
                time.sleep(self.delay)

    def _on_request(self, req: PendingRequest) -> None:
        with self._lock:
            self.pending = req
            if self.hotseat and self.active_seat != req.player:
                self.handoff_pending = req.player
        self._broadcast(lambda v: {"type": "request", **self.render_request(v)})

    # ------------------------------------------------------------------ human actions (HTTP thread)
    def act(self, player: str, request_id: int, action: dict[str, Any] | None, card: str | None) -> None:
        with self._lock:
            req = self.pending
            if req is None or req.request_id != request_id or req.player != player:
                raise LookupError("no such pending request")
            if self.hotseat and self.handoff_pending == player:
                raise PermissionError("acknowledge the hot-seat handoff first")
            if req.kind == "card":
                if card not in req.cards:
                    raise IllegalAction(f"{card!r} cannot be shown")
                self.pending = None
                req.reply.put(card)
                return
            if not action:
                raise IllegalAction("action required")
            act = Action(**{**action, "player": player})
            if not is_legal(self.gm.state, act) or act.key() not in {a.key() for a in req.legal}:
                raise IllegalAction(f"{act.key()} is not legal now")
            self.pending = None
            req.reply.put(act)

    # ------------------------------------------------------------------ remote seats: presence / lobby gate
    def waiting_for(self) -> list[str]:
        if not self.remote or self.started.is_set():
            return []
        return [p for p in self.humans if p not in self.joined]

    def force_start(self) -> None:
        self.started.set()
        self._broadcast(lambda v: {"type": "presence", **self.render_presence()})

    def _touch_presence(self, viewer: str, delta: int) -> None:
        if viewer not in self.presence:
            return
        self.presence[viewer] = max(0, self.presence[viewer] + delta)
        if delta > 0:
            self.joined.add(viewer)
        if self.remote and not self.waiting_for():
            self.started.set()
        self._broadcast(lambda v: {"type": "presence", **self.render_presence()})

    def render_presence(self) -> dict[str, Any]:
        return {"presence": dict(self.presence), "waiting_for": self.waiting_for(), "started": self.started.is_set() or not self.remote}

    def acknowledge_seat(self, player: str) -> None:
        with self._lock:
            if player not in self.humans:
                raise PermissionError("not a human seat")
            self.active_seat = player
            if self.handoff_pending == player:
                self.handoff_pending = None
        self._broadcast(lambda v: {"type": "request", **self.render_request(v)})

    def set_pause(self, paused: bool) -> None:
        self.paused = paused
        self._broadcast(lambda v: {"type": "control", "paused": self.paused, "delay": self.delay})

    def set_delay(self, delay: float) -> None:
        self.delay = max(0.0, min(5.0, delay))
        self._broadcast(lambda v: {"type": "control", "paused": self.paused, "delay": self.delay})

    def coach(self, player: str) -> dict[str, Any]:
        with self._lock:
            self.coach_used[player] = self.coach_used.get(player, 0) + 1
            self.gm.log_agent_note(player, {"summary": "coach_mode_on", "count": self.coach_used[player]})
            req = self.pending if (self.pending and self.pending.player == player and self.pending.kind == "action") else None
            return coach_hints(self.gm, player, req.observation if req else None, req.legal if req else None)

    def add_note(self, player: str, note: str) -> list[str]:
        with self._lock:
            nb = self.gm.notebooks[player]
            nb.notes.append(note)
            return list(nb.notes)

    # ------------------------------------------------------------------ subscriptions
    def subscribe(self, viewer: str, cb: Subscriber) -> int:
        with self._lock:
            self._sub_seq += 1
            self._subs[self._sub_seq] = (viewer, cb)
            self.idle_since = None
            sub_id = self._sub_seq
        self._touch_presence(viewer, +1)
        return sub_id

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            ent = self._subs.pop(sub_id, None)
            if not self._subs:
                self.idle_since = time.time()
        if ent is not None:
            self._touch_presence(ent[0], -1)

    def _broadcast(self, make: Any) -> None:
        with self._lock:
            subs = list(self._subs.values())
        cache: dict[str, dict[str, Any]] = {}
        for viewer, cb in subs:
            if viewer not in cache:
                cache[viewer] = make(viewer)
            try:
                cb(cache[viewer])
            except Exception:
                pass

    # ------------------------------------------------------------------ rendering (the only outbound path)
    def _viewer_pid(self, viewer: str) -> str | None:
        return None if viewer in (OMNI, TABLE) else viewer

    def _seat_visible(self, viewer: str) -> bool:
        """Hot-seat: a human seat's private data is only sent while it holds the device."""
        if viewer in (OMNI, TABLE) or viewer not in self.humans or not self.hotseat:
            return True
        return self.active_seat == viewer and self.handoff_pending != viewer

    def render_state(self, viewer: str, light: bool = False) -> dict[str, Any]:
        """`light=True` skips the (solver-based) candidate counts - used for per-action frames."""
        gm = self.gm
        st = gm.state
        sus = suspects(st.config.edition)
        pid = self._viewer_pid(viewer)
        players = [
            {
                "id": q.id,
                "name": next((s.name for s in gm.specs if s.id == q.id), None),
                "label": next((s.display_label() for s in gm.specs if s.id == q.id), q.id),
                "kind": next((s.kind for s in gm.specs if s.id == q.id), "baseline"),
                "suspect_token": sus[q.seat],
                "position": q.position,
                "eliminated": q.eliminated,
                "hand_size": len(q.hand),
                "team": st.config.team_of(q.id) if st.config.teams else None,
            }
            for q in st.players
        ]
        out: dict[str, Any] = {
            "id": self.id,
            "seed": gm.seed,
            "viewer": viewer,
            "seat_visible": self._seat_visible(viewer),
            "turn": {
                "number": st.turn_number,
                "current_player": st.current_player().id,
                "phase": st.phase,
                "roll": st.roll,
                "pending_suggestion": st.pending_suggestion.model_dump() if st.pending_suggestion else None,
                "acting": gm.acting_player() if not gm.finished else None,
            },
            "board": {"token_positions": dict(st.token_positions), "weapon_positions": dict(st.weapon_positions), "players": players},
            "cards": {"suspects": list(sus), "weapons": list(weapons(st.config.edition)), "rooms": list(rooms(st.config.edition)), "faceup": list(st.faceup)},
            "config": st.config.model_dump(),
            "finished": gm.finished,
            "winner": gm.winner,
            "paused": self.paused,
            "delay": self.delay,
            "humans": list(self.humans),
            "hotseat": self.hotseat,
            "remote": self.remote,
            **self.render_presence(),
            "active_seat": self.active_seat,
            "handoff_pending": self.handoff_pending,
            "n_events": len(gm.events),
            "illegal_attempts": dict(gm.illegal_attempts),
            "error": self.error,
            "stopped": self.stopping and not gm.finished,
            "autosave": self.autosave,
            "ponder": self._ponder_stats(),
            "llm": {p: {**a.stats, "cost_usd": round(getattr(a, "cost_usd", 0.0), 5)} for p, a in self.agents.items() if getattr(a, "kind", "") == "llm" and hasattr(a, "stats")},
        }
        if pid is not None and self._seat_visible(viewer):
            p = st.player(pid)
            out["you"] = {"id": pid, "hand": list(p.hand), "position": p.position, "eliminated": p.eliminated, "may_suggest": p.may_suggest, "suspect_token": sus[p.seat]}
            out["notebook"] = gm.notebooks[pid].model_dump()
            out["candidates"] = None if light else self._candidates(pid)
        elif viewer == OMNI:
            out["omniscient"] = self.render_omniscient(light)
        return out

    def _ponder_stats(self) -> dict[str, Any]:
        pm = getattr(self.gm, "_ponder_manager", None)
        return dict(getattr(pm, "stats", {}) or {}) if pm else dict(self.gm.ponder_stats)

    def _candidates(self, pid: str) -> int | None:
        try:
            from clue.tools.solver import solve

            st = self.gm.state
            sizes = {q.id: len(q.hand) for q in st.players}
            return len(solve(self.gm.notebooks[pid], self.gm.player_ids(), sizes, st.config.edition).combos)
        except Exception:
            return None

    def render_omniscient(self, light: bool = False) -> dict[str, Any]:
        st = self.gm.state
        players = [p.id for p in st.players]
        holder = {c: p.id for p in st.players for c in p.hand}
        for c in st.faceup:
            holder[c] = "face-up"
        for c in st.solution:
            holder[c] = "ENVELOPE"
        rows = []
        ed = st.config.edition
        for cat in (list(suspects(ed)), list(weapons(ed)), list(rooms(ed))):
            for c in cat:
                knows = {}
                for p in players:
                    nb = self.gm.notebooks[p]
                    if c in nb.my_hand:
                        knows[p] = "mine"
                    elif c in nb.known_holder:
                        knows[p] = nb.known_holder[c]
                    elif all(c in nb.not_held.get(q, []) for q in players if q != p):
                        knows[p] = "env!"
                    else:
                        knows[p] = "?" + "x" * sum(1 for q in players if q != p and c in nb.not_held.get(q, []))
                rows.append({"card": c, "truth": holder.get(c, "?"), "knows": knows})
        return {"solution": list(st.solution), "hands": {p.id: list(p.hand) for p in st.players}, "rows": rows, "candidates": {p: (None if light else self._candidates(p)) for p in players}}

    def render_events(self, viewer: str, since: int = 0) -> list[dict[str, Any]]:
        pid = self._viewer_pid(viewer)
        out = []
        for i, e in enumerate(self.gm.events[since:], start=since):
            if viewer == OMNI:
                d: dict[str, Any] = {"type": e.type, "turn": e.turn, "player": e.player, **e.public, **e.private}
            elif pid is not None and self._seat_visible(viewer):
                if not e.visible_to(pid):
                    continue
                d = dict(e.redacted_for(pid))
            else:
                # spectators/table view: not players, so private_disproofs does not apply to them — they see the
                # full disproof round (who passed / who showed) but still no private cards
                d = dict(e.redacted_for(None))
                if e.type == "disproved" and self.gm.config.private_disproofs:
                    d["disprover"] = e.private.get("disprover")
            d["seq"] = i
            d["text"] = describe_event(d)
            out.append(d)
        return out

    def render_request(self, viewer: str) -> dict[str, Any]:
        with self._lock:
            req = self.pending
            base: dict[str, Any] = {"pending_for": req.player if req else None, "handoff_pending": self.handoff_pending, "active_seat": self.active_seat}
            if req is None or req.player != viewer or not self._seat_visible(viewer):
                return {**base, "request": None}
            return {
                **base,
                "request": {
                    "request_id": req.request_id,
                    "kind": req.kind,
                    "legal": [a.model_dump(exclude_none=True) for a in req.legal],
                    "cards": list(req.cards),
                    "pending_suggestion": req.observation["turn"].get("pending_suggestion"),
                    "roll": req.observation["turn"].get("roll"),
                },
            }

    def render_frame(self, viewer: str) -> dict[str, Any]:
        """Full snapshot for a (re)connecting client."""
        return {
            "type": "snapshot",
            "state": self.render_state(viewer),
            "events": self.render_events(viewer),
            **self.render_request(viewer),
            **({"finished": self.render_finished(viewer)} if self.gm.finished else {}),
        }

    def render_finished(self, viewer: str) -> dict[str, Any]:
        s = self.summary or self.gm.summary()
        return {"summary": s, "replays": list(self.replay_paths), "solution": list(self.gm.state.solution)}


def build_agents(specs: list[PlayerSpec], seed: int, provider: str | None) -> dict[str, PlayerAgent]:
    """Factory wrapper: human seats become WebHumanAgents; everything else via the normal factory."""
    from clue.agents.factory import make_agent

    agents: dict[str, PlayerAgent] = {}
    for i, s in enumerate(specs):
        agents[s.id] = WebHumanAgent(s.id) if s.kind == "human" else make_agent(s, seed=seed + i, provider=provider)
    return agents


__all__ = ["OMNI", "TABLE", "GameSession", "build_agents", "queue"]

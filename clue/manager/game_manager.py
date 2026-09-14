"""GameManager: stateful orchestrator over the pure rules engine.

Adds seeded RNG, per-player notebooks/observations, privacy redaction, a full event log
(with redacted + unredacted views), save/load and JSONL replay export.
Contains NO strategy text and NO LLM code.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from clue.manager.notebook import Notebook
from clue.rules import Action, Event, GameConfig, GameState, apply_action, legal_actions, new_game
from clue.rules import board as B
from clue.rules.cards import rooms, suspects, weapons


class PlayerSpec(BaseModel):
    id: str
    name: str | None = None
    kind: str = "baseline"  # human | llm | baseline
    bot: str | None = None
    model: str | None = None
    strategy: str | None = None
    temperature: float | None = None
    tools: bool = True
    tool_mode: str | None = None  # precomputed | native | none (None -> precomputed when tools=True)
    prompt_profile: str = "full"  # full | compact

    def label(self) -> str:
        parts = [self.kind]
        if self.kind == "llm":
            parts.append(self.model or "mock")
            if self.strategy:
                parts.append(Path(self.strategy).stem)
            if not self.tools or self.tool_mode == "none":
                parts.append("no-tools")
            elif self.tool_mode == "native":
                parts.append("native")
            if self.prompt_profile != "full":
                parts.append(self.prompt_profile)
        elif self.kind == "baseline":
            parts.append(self.bot or "heuristic")
        return ":".join(parts)


class LogRecord(BaseModel):
    seq: int
    kind: str  # "event" | "action" | "tool_call" | "agent_note" | "ponder"
    data: dict[str, Any]
    private: dict[str, Any] = Field(default_factory=dict)
    private_to: list[str] = Field(default_factory=list)
    hidden: bool = False  # existence itself is private (see Event.hidden)


class GameManager:
    def __init__(self, config: GameConfig, specs: list[PlayerSpec], seed: int) -> None:
        self.config = config
        self.specs = specs
        self.seed = seed
        self.rng = random.Random(seed)
        self.state: GameState = new_game(config, [s.id for s in specs], self.rng)
        self.log: list[LogRecord] = []
        self.events: list[Event] = []
        self.notebooks: dict[str, Notebook] = {}
        self.action_count = 0
        self.illegal_attempts: dict[str, int] = {}
        self.ponder_stats: dict[str, dict[str, int]] = {}
        self._ponder_manager: Any = None
        self._saved_agent_state: dict[str, Any] = {}
        for p in self.state.players:
            self.notebooks[p.id] = self._fresh_notebook(p.id)
        self._record(
            Event(
                type="game_start",
                turn=0,
                public={
                    "seed": seed,
                    "players": [s.model_dump() for s in specs],
                    "config": config.model_dump(),
                    "faceup": list(self.state.faceup),
                    "weapon_positions": dict(self.state.weapon_positions),
                },
                private={"solution": list(self.state.solution), "hands": {p.id: p.hand for p in self.state.players}},
            )
        )
        self._record(Event(type="turn_start", turn=0, player=self.state.current_player().id))

    def _fresh_notebook(self, pid: str) -> Notebook:
        """Notebook seeded with the viewer's hand — and, in team mode, every teammate's hand."""
        team = self.config.team_of(pid)
        nb = Notebook(viewer=pid, team=team if len(team) > 1 else [], faceup=list(self.state.faceup))
        for q in team:
            hand = self.state.player(q).hand
            nb.my_hand.extend(hand)
            for c in hand:
                nb.known_holder[c] = q
        nb.my_hand.sort()
        return nb

    # ------------------------------------------------------------------ factory
    @classmethod
    def create(cls, players: list[PlayerSpec] | list[dict[str, Any]], seed: int = 0, config: GameConfig | None = None) -> GameManager:
        specs = [p if isinstance(p, PlayerSpec) else PlayerSpec(**p) for p in players]
        cfg = config or GameConfig(num_players=len(specs))
        if cfg.num_players != len(specs):
            cfg = cfg.model_copy(update={"num_players": len(specs)})
        return cls(cfg, specs, seed)

    # ------------------------------------------------------------------ core
    @property
    def finished(self) -> bool:
        return self.state.finished

    @property
    def winner(self) -> str | None:
        return self.state.winner

    def player_ids(self) -> list[str]:
        return [p.id for p in self.state.players]

    def acting_player(self) -> str:
        """Whose decision is needed now (disprover during disprove phase, else current player)."""
        st = self.state
        if st.phase == "disprove" and st.disprover_index is not None:
            return st.players[st.disprover_index].id
        return st.current_player().id

    def legal_actions(self, player_id: str, include_accusations: bool = True) -> list[Action]:
        return legal_actions(self.state, player_id, include_accusations)

    def step(self, action: Action) -> list[Event]:
        """Apply an action. Raises IllegalAction (and counts it) if illegal."""
        try:
            new_state, events = apply_action(self.state, action, self.rng)
        except Exception:
            self.illegal_attempts[action.player] = self.illegal_attempts.get(action.player, 0) + 1
            raise
        self.state = new_state
        self.action_count += 1
        data = action.model_dump(exclude_none=True)
        if action.type == "show_card" and self.state.pending_suggestion is None and events:
            # keep the shown card private to suggester + shower, like the matching `disproved` event
            ev = next((e for e in events if e.type == "disproved"), None)
            priv = {"card": data.pop("card")}
            if self.config.private_disproofs:  # C: the shower's identity is private too
                priv["player"] = data.pop("player")
                data["player"] = None
            self.log.append(LogRecord(seq=len(self.log), kind="action", data=data, private=priv, private_to=list(ev.private_to) if ev else []))
        else:
            self.log.append(LogRecord(seq=len(self.log), kind="action", data=data))
        for ev in events:
            self._record(ev)
        return events

    def log_tool_call(self, player_id: str, tool: str, args: dict[str, Any], result: Any) -> None:
        self.log.append(LogRecord(seq=len(self.log), kind="tool_call", data={"player": player_id, "tool": tool, "args": args}, private={"result": result}, private_to=[player_id]))

    def log_agent_note(self, player_id: str, note: dict[str, Any]) -> None:
        """Record LLM reasoning / retries / fallbacks (private to that player)."""
        self.log.append(LogRecord(seq=len(self.log), kind="agent_note", data={"player": player_id, "summary": note.get("summary", "")}, private=note, private_to=[player_id]))

    def log_ponder(self, player_id: str, summary: dict[str, Any]) -> None:
        """Record one background-thinking session (private to that player)."""
        self.log.append(
            LogRecord(
                seq=len(self.log),
                kind="ponder",
                data={"player": player_id, "stopped_by": summary.get("stopped_by"), "duration_ms": summary.get("duration_ms")},
                private=summary,
                private_to=[player_id],
            )
        )

    def _record(self, ev: Event) -> None:
        self.events.append(ev)
        self.log.append(LogRecord(seq=len(self.log), kind="event", data=ev.redacted_for(None), private=ev.private, private_to=ev.private_to, hidden=ev.hidden))
        for pid, nb in self.notebooks.items():
            if ev.visible_to(pid):
                nb.ingest(ev.redacted_for(pid), self.player_ids())

    # ------------------------------------------------------------------ observations
    def public_history(self, viewer: str | None, last_n: int | None = None) -> list[dict[str, Any]]:
        evs = [e.redacted_for(viewer) for e in self.events if e.type not in ("game_start",) and e.visible_to(viewer)]
        return evs[-last_n:] if last_n else evs

    def get_observation(self, player_id: str, history_limit: int | None = None) -> dict[str, Any]:
        st = self.state
        p = st.player(player_id)
        acts = self.legal_actions(player_id, include_accusations=False)
        sus = suspects(st.config.edition)
        pending = st.pending_suggestion.model_dump() if st.pending_suggestion else None
        return {
            "you": {
                "id": p.id,
                "name": next((s.name for s in self.specs if s.id == p.id), None),
                "suspect_token": sus[p.seat],
                "hand": list(p.hand),
                "team": self.config.team_of(p.id) if self.config.teams else None,
                "team_hands": {q: list(st.player(q).hand) for q in self.config.team_of(p.id) if q != p.id} if self.config.teams else None,
                "skip_turns": p.skip_turns,
                "position": p.position,
                "in_room": B.is_room(p.position),
                "eliminated": p.eliminated,
                "may_suggest": p.may_suggest,
            },
            "board": {
                "token_positions": dict(st.token_positions),
                "weapon_positions": dict(st.weapon_positions),
                "players": [
                    {
                        "id": q.id,
                        "suspect_token": sus[q.seat],
                        "position": q.position,
                        "eliminated": q.eliminated,
                        "hand_size": len(q.hand),
                        "team": self.config.team_of(q.id) if self.config.teams else None,
                    }
                    for q in st.players
                ],
                "secret_passages": dict(B.passages_for(st.config.edition)),
                "your_legal_moves": [a.to for a in acts if a.type == "move"],
            },
            "turn": {
                "number": st.turn_number,
                "current_player": st.current_player().id,
                "phase": st.phase,
                "roll": st.roll,
                "pending_suggestion": pending,
                "you_are_acting": self.acting_player() == player_id,
            },
            "public_history": self.public_history(player_id, history_limit),
            "notebook": self.notebooks[player_id].model_dump(),
            "legal_actions": [a.model_dump(exclude_none=True) for a in acts],
            "can_accuse": any(a.type != "show_card" for a in acts) and st.phase != "disprove",
            "cards": {"suspects": list(sus), "weapons": list(weapons(st.config.edition)), "rooms": list(rooms(st.config.edition)), "faceup": list(st.faceup)},
            "config": st.config.model_dump(),
        }

    # ------------------------------------------------------------------ replay / persistence
    def export_replay(self, viewer: str | None = None) -> list[dict[str, Any]]:
        """Full log. viewer=None -> unredacted (God view). viewer=pid -> redacted for that player."""
        out = []
        for rec in self.log:
            if rec.hidden and viewer is not None and viewer not in rec.private_to:
                continue
            d: dict[str, Any] = {"seq": rec.seq, "kind": rec.kind, **rec.data}
            if viewer is None or viewer in rec.private_to:
                d.update(rec.private)
            elif rec.kind in ("tool_call", "agent_note", "ponder"):
                continue  # other players' private reasoning is invisible
            out.append(d)
        return out

    def replay_hash(self) -> str:
        payload = json.dumps(self.export_replay(None), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def write_replay(self, path: str | Path, viewer: str | None = None) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            if path.suffix == ".jsonl":
                for rec in self.export_replay(viewer):
                    f.write(json.dumps(rec) + "\n")
            else:
                json.dump(self.export_replay(viewer), f, indent=1)
        return path

    SAVE_FORMAT = 2

    def save(self, path: str | Path, agents: dict[str, Any] | None = None) -> Path:
        """Checkpoint the full game (state, RNG, event/audit log) plus each agent's private memory.

        Safe points: between actions. Saving mid-`disprove` is fine too - the pending suggestion is part of state.
        Notebooks are rebuilt from the event log on load; only the free-form `notes` are stored explicitly.
        """
        data = {
            "format": self.SAVE_FORMAT,
            "seed": self.seed,
            "rng": self.rng.getstate(),
            "config": self.config.model_dump(),
            "specs": [s.model_dump() for s in self.specs],
            "state": self.state.model_dump(),
            "events": [e.model_dump() for e in self.events],
            "log": [r.model_dump() for r in self.log],
            "action_count": self.action_count,
            "illegal_attempts": dict(self.illegal_attempts),
            "ponder_stats": dict(self.ponder_stats),
            "notes": {pid: list(nb.notes) for pid, nb in self.notebooks.items()},
            "agents": {pid: a.export_state() for pid, a in (agents or {}).items() if hasattr(a, "export_state")},
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, default=_json_default))
        tmp.replace(p)  # atomic: a crash mid-write never corrupts the previous save
        return p

    @classmethod
    def load(cls, path: str | Path) -> GameManager:
        data = json.loads(Path(path).read_text())
        gm = cls.__new__(cls)
        gm.config = GameConfig(**data["config"])
        gm.specs = [PlayerSpec(**s) for s in data["specs"]]
        gm.seed = data["seed"]
        gm.rng = random.Random()
        s0, s1, s2 = data["rng"]
        gm.rng.setstate((s0, tuple(s1), s2))
        gm.state = GameState(**data["state"])
        gm.events = [Event(**e) for e in data["events"]]
        gm.log = [LogRecord(**r) for r in data["log"]]
        gm.action_count = data["action_count"]
        gm.illegal_attempts = dict(data.get("illegal_attempts", {}))
        gm.ponder_stats = dict(data.get("ponder_stats", {}))
        gm._ponder_manager = None
        gm.notebooks = {p.id: gm._fresh_notebook(p.id) for p in gm.state.players}
        for ev in gm.events:
            for pid, nb in gm.notebooks.items():
                if ev.visible_to(pid):
                    nb.ingest(ev.redacted_for(pid), gm.player_ids())
        for pid, notes in data.get("notes", {}).items():
            if pid in gm.notebooks:
                gm.notebooks[pid].notes = list(notes)
        gm._saved_agent_state = dict(data.get("agents", {}))
        return gm

    def restore_agents(self, agents: dict[str, Any]) -> list[str]:
        """Push saved private memory back into freshly constructed agents; returns the ids restored."""
        saved = getattr(self, "_saved_agent_state", {})
        done = []
        for pid, a in agents.items():
            if pid in saved and hasattr(a, "import_state"):
                a.import_state(saved[pid])
                done.append(pid)
        return done

    # ------------------------------------------------------------------ stats
    def summary(self) -> dict[str, Any]:
        acc = [e for e in self.events if e.type == "accuse"]
        return {
            "seed": self.seed,
            "winner": self.winner,
            "winning_team": self.config.team_of(self.winner) if self.winner and self.config.teams else None,
            "solution": list(self.state.solution),
            "turns": self.state.turn_number,
            "actions": self.action_count,
            "suggestions": {pid: self.notebooks[pid].suggestions_made.get(pid, 0) for pid in self.player_ids()},
            "false_accusations": [e.player for e in acc if not e.public.get("correct")],
            "eliminated": [p.id for p in self.state.players if p.eliminated],
            "illegal_attempts": dict(self.illegal_attempts),
            "ponder": dict(self.ponder_stats),
            "labels": {s.id: s.label() for s in self.specs},
        }


def _json_default(o: Any) -> Any:
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(str(type(o)))

"""An opened replay: precomputed per-event frames, redacted per requested viewer on demand."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clue.agents.human import describe_event
from clue.replay.state import ReplayState, load_replay


class ReplaySession:
    def __init__(self, rid: str, path: Path) -> None:
        self.id = rid
        self.path = path
        self.records = load_replay(path)
        self.state = ReplayState(self.records)
        # private reasoning records (tool calls, agent notes, ponder) belong to one seat each
        self.private_records = [r for r in self.records if r.get("kind") in ("tool_call", "agent_note", "ponder")]
        self.omniscient = any("hands" in r for r in self.records if r.get("type") == "game_start")

    def info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.path.name,
            "n_events": len(self.state.events),
            "players": self.state.players,
            "viewers": (["__omni__"] if self.omniscient else []) + [p["id"] for p in self.state.players],
            "edition": self.state.edition,
        }

    def frames(self, viewer: str | None) -> dict[str, Any]:
        """All frames for a viewer: board/token state after each event plus the redacted event text.
        Redaction: unredacted files contain private fields inline (the writer already dropped them for redacted files);
        for a seat viewer we keep an event's private fields only when it names that seat in `private_to`-derived keys."""
        st = self.state
        st.reset()
        frames = [self._frame(st, None, viewer)]
        for ev in st.events:
            st.apply(ev)
            st.idx += 1
            frames.append(self._frame(st, ev, viewer))
        pub: dict[str, Any] = {"hands": {}, "solution": []}
        if viewer == "__omni__" and self.omniscient:
            pub = {"hands": st.hands, "solution": st.solution}
        elif viewer and viewer in st.hands:
            pub = {"hands": {viewer: st.hands[viewer]}, "solution": []}
        notes = [r for r in self.private_records if viewer == "__omni__" or r.get("player") == viewer]
        return {"info": self.info(), "frames": frames, **pub, "seat": st.seat, "weapon_start": st.weapon_start, "private_records": notes}

    @staticmethod
    def _redact(ev: dict[str, Any], viewer: str | None) -> dict[str, Any]:
        d = dict(ev)
        if viewer == "__omni__":
            return d
        if d.get("type") == "disproved" and "card" in d:
            # the shown card is private to suggester + shower
            if viewer not in (d.get("suggester"), d.get("disprover")):
                d.pop("card", None)
        return d

    def _frame(self, st: ReplayState, ev: dict[str, Any] | None, viewer: str | None) -> dict[str, Any]:
        e = self._redact(ev, viewer) if ev else None
        return {
            "idx": st.idx,
            "tokens": dict(st.tokens),
            "weapons": dict(st.weapons),
            "eliminated": sorted(st.eliminated),
            "event": e,
            "text": describe_event(e) if e else "Game start",
        }

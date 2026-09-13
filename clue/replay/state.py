"""Replay records -> board/knowledge state at any event index. Pure Python, no UI dependency."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clue.rules import board as B
from clue.rules.cards import rooms, suspects, weapons


def load_replay(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    text = p.read_text()
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return list(data) if isinstance(data, list) else list(data.get("records", []))


class ReplayState:
    """Replays public events to reconstruct token / weapon positions and per-player knowledge summaries."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        start = next((r for r in records if r.get("type") == "game_start"), {})
        self.edition = str((start.get("config") or {}).get("edition", "classic"))
        self.players: list[dict[str, Any]] = list(start.get("players", []))
        self.suspects = list(suspects(self.edition))
        self.hands: dict[str, list[str]] = dict(start.get("hands", {}))
        self.solution: list[str] = list(start.get("solution", []))
        self.weapon_start: dict[str, str] = dict(start.get("weapon_positions", {})) or {w: rooms(self.edition)[i % len(rooms(self.edition))] for i, w in enumerate(weapons(self.edition))}
        self.events = [r for r in records if r.get("kind") == "event" and r.get("type") != "game_start"]
        self.reset()

    def reset(self) -> None:
        n = len(self.players)
        self.tokens = {s: B.sq(*B.board_for(self.edition).starts[i]) for i, s in enumerate(self.suspects)}
        self.weapons = dict(self.weapon_start)
        self.seat = {p["id"]: self.suspects[i] for i, p in enumerate(self.players[:n])}
        self.idx = 0
        self.eliminated: set[str] = set()
        self.last_suggestion: dict[str, Any] | None = None

    def apply(self, ev: dict[str, Any]) -> None:
        t, who = ev.get("type"), ev.get("player")
        if t in ("move", "passage") and who in self.seat:
            self.tokens[self.seat[str(who)]] = str(ev["to"])
        elif t == "suggest":
            self.tokens[str(ev["suspect"])] = str(ev["room"])
            self.weapons[str(ev["weapon"])] = str(ev["room"])
            self.last_suggestion = ev
        elif t == "eliminated" and who:
            self.eliminated.add(str(who))

    def seek(self, idx: int) -> None:
        idx = max(0, min(idx, len(self.events)))
        if idx < self.idx:
            self.reset()
        while self.idx < idx:
            self.apply(self.events[self.idx])
            self.idx += 1

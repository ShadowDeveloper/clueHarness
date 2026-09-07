"""Pydantic schemas for game config, state, actions and events. Pure data."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from clue.rules.cards import Edition

Phase = Literal["move", "suggest", "accuse", "disprove", "end"]


class GameConfig(BaseModel):
    edition: Edition = "classic"
    dice: Literal[1, 2] = 2
    deal_remainder: Literal["uneven", "faceup"] = "uneven"
    num_players: int = Field(4, ge=3, le=6)
    max_turns: int = 400


class PlayerState(BaseModel):
    id: str
    seat: int  # 0..5 canonical suspect index
    hand: list[str] = Field(default_factory=list)
    position: str
    eliminated: bool = False
    # entered a room this turn / was moved into a room by a suggestion since last turn
    may_suggest: bool = False
    # room this player left this turn (may not re-enter)
    left_room: str | None = None


class Suggestion(BaseModel):
    suggester: str
    suspect: str
    weapon: str
    room: str


class GameState(BaseModel):
    config: GameConfig
    players: list[PlayerState]
    solution: tuple[str, str, str]  # (suspect, weapon, room)
    faceup: list[str] = Field(default_factory=list)
    token_positions: dict[str, str]  # suspect name -> position (all 6)
    weapon_positions: dict[str, str]  # weapon -> room
    current: int = 0  # index into players
    phase: Phase = "move"
    turn_number: int = 0
    roll: int | None = None
    has_moved: bool = False
    pending_suggestion: Suggestion | None = None
    disprover_index: int | None = None  # index of player currently asked to disprove
    winner: str | None = None
    finished: bool = False
    last_suggestion_room_visitors: list[str] = Field(default_factory=list)

    def player(self, pid: str) -> PlayerState:
        for p in self.players:
            if p.id == pid:
                return p
        raise KeyError(pid)

    def current_player(self) -> PlayerState:
        return self.players[self.current]

    def index_of(self, pid: str) -> int:
        return next(i for i, p in enumerate(self.players) if p.id == pid)


# --- actions -------------------------------------------------------------


class Action(BaseModel):
    type: Literal["roll", "move", "passage", "suggest", "accuse", "show_card", "end_turn"]
    player: str
    to: str | None = None  # move destination
    suspect: str | None = None
    weapon: str | None = None
    room: str | None = None
    card: str | None = None  # show_card

    def key(self) -> str:
        parts: list[str] = [self.type]
        for f in ("to", "suspect", "weapon", "room", "card"):
            v = getattr(self, f)
            if v is not None:
                parts.append(f"{f}={v}")
        return " ".join(parts)


class Event(BaseModel):
    """One audit-log event. `private_to` lists player ids allowed to see `private` fields."""

    type: str
    turn: int
    player: str | None = None
    public: dict[str, object] = Field(default_factory=dict)
    private: dict[str, object] = Field(default_factory=dict)
    private_to: list[str] = Field(default_factory=list)

    def redacted_for(self, viewer: str | None) -> dict[str, object]:
        d: dict[str, object] = {"type": self.type, "turn": self.turn, "player": self.player, **self.public}
        if viewer is not None and viewer in self.private_to:
            d.update(self.private)
        return d


class IllegalAction(Exception):
    """Raised by the rules engine for any action not in legal_actions."""

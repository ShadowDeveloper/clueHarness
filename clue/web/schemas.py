"""Explicit request/response schemas for the web API (mirrored to TypeScript from /api/openapi.json)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from clue.manager.game_manager import PlayerSpec
from clue.rules import GameConfig


class CreateGame(BaseModel):
    players: list[PlayerSpec] | None = None
    players_arg: str | None = Field(None, description="CLI shorthand, e.g. 'human,baseline:expert,llm:aggressive'")
    seed: int | None = None
    config: GameConfig | None = None
    ponder: bool = False
    ponder_grace: float = 2.0
    delay: float = 0.6
    provider: str | None = None
    autosave: bool = True
    resume: str | None = Field(None, description="checkpoint file name inside the saves dir")
    remote: bool = Field(False, description="each human seat gets its own invite link (several browsers); game waits until all seats joined")


class GameCreated(BaseModel):
    id: str
    owner_token: str
    spectator_token: str
    seat_tokens: dict[str, str] = Field(default_factory=dict, description="remote games: per-human-seat invite tokens")
    remote: bool = False
    seats: list[dict[str, Any]]
    humans: list[str]
    resumed: bool = False
    restored: list[str] = Field(default_factory=list)


class ActBody(BaseModel):
    request_id: int
    action: dict[str, Any] | None = None
    card: str | None = None
    player: str | None = None  # hot-seat: which human seat is answering (default: the only/active one)


class ControlBody(BaseModel):
    pause: bool | None = None
    delay: float | None = None
    acknowledge_seat: str | None = None  # hot-seat handoff
    start: bool | None = None  # remote: host starts without waiting for every seat to join


class NoteBody(BaseModel):
    note: str = Field(min_length=1, max_length=500)
    player: str | None = None


class SaveBody(BaseModel):
    name: str | None = Field(None, pattern=r"^[A-Za-z0-9_.-]{1,64}$")


class OkPath(BaseModel):
    ok: bool = True
    path: str | None = None


class GameListItem(BaseModel):
    id: str
    seed: int
    players: list[str]
    labels: dict[str, str]
    humans: list[str]
    finished: bool
    turn: int
    created: float
    winner: str | None
    remote: bool = False
    presence: dict[str, int] = Field(default_factory=dict)
    waiting_for: list[str] = Field(default_factory=list)


class OpenReplay(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.(jsonl|json)$")


class ReplayInfo(BaseModel):
    id: str
    name: str
    n_events: int
    players: list[dict[str, Any]]
    viewers: list[str]
    edition: str


class CreateTournament(BaseModel):
    players: list[PlayerSpec] | None = None
    players_arg: str | None = None
    games: int = Field(20, ge=1, le=10_000)
    seed: int = 0
    workers: int = Field(1, ge=0, le=64)
    ponder: bool = False
    provider: str | None = None
    max_usd: float | None = None
    config: GameConfig | None = None
    probe: bool = True


class TournamentStatus(BaseModel):
    id: str
    status: Literal["running", "finished", "cancelled", "error"]
    games: int
    done: int
    seed: int
    players: list[str]
    started: float
    finished_at: float | None
    error: str | None
    report: dict[str, Any] | None  # aggregate of the games done so far
    cost: dict[str, Any]

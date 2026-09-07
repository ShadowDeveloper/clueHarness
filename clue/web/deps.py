"""Shared FastAPI dependencies: registry/settings access, token -> role/viewer resolution."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Query, Request

from clue.web.auth import role_of
from clue.web.game_session import OMNI, TABLE, GameSession
from clue.web.sessions import Registry
from clue.web.settings import WebSettings


def registry(request: Request) -> Registry:
    reg: Registry = request.app.state.registry
    return reg


def settings(request: Request) -> WebSettings:
    s: WebSettings = request.app.state.settings
    return s


@dataclass
class Access:
    session: GameSession
    role: str  # owner | spectator
    viewer: str  # seat id | OMNI | TABLE

    def human_seat(self, requested: str | None) -> str:
        """Which human seat an owner acts for (hot-seat: any human seat; otherwise the single one)."""
        if self.role != "owner":
            raise HTTPException(403, "spectators cannot act")
        if not self.session.humans:
            raise HTTPException(409, "no human seat in this game")
        seat = requested or (self.session.active_seat if self.session.hotseat else self.session.humans[0])
        if seat not in self.session.humans:
            raise HTTPException(403, f"{seat} is not a human seat")
        if len(self.session.humans) > 1 and not self.session.hotseat and seat != self.session.humans[0]:
            raise HTTPException(403, "hot-seat mode is disabled")
        return seat


def resolve_viewer(sess: GameSession, role: str, view: str | None) -> str:
    """Token role + optional requested view -> the viewer whose redaction is applied. Never trusts `view` blindly."""
    if role == "owner":
        if sess.humans:
            if view in sess.humans and (sess.hotseat or view == sess.humans[0]):
                return view
            return sess.active_seat or sess.humans[0]
        # bots only: owner may watch omnisciently or through any seat
        return view if view in sess.gm.player_ids() else OMNI
    # spectator
    if sess.humans:
        return TABLE
    return view if view in sess.gm.player_ids() else OMNI


def access(request: Request, game_id: str, k: str | None = Query(None), view: str | None = Query(None)) -> Access:
    reg = registry(request)
    sess = reg.games.get(game_id)
    if sess is None:
        raise HTTPException(404, "game not found")
    role = role_of(settings(request).secret, game_id, k)
    if role is None:
        raise HTTPException(403, "invalid or missing token")
    return Access(sess, role, resolve_viewer(sess, role, view))


__all__ = ["OMNI", "TABLE", "Access", "access", "registry", "resolve_viewer", "settings"]

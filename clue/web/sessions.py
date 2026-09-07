"""In-memory registry of game / replay / tournament sessions + simple per-IP rate limit."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from clue.web.auth import new_id
from clue.web.game_session import GameSession
from clue.web.replay_session import ReplaySession
from clue.web.settings import WebSettings
from clue.web.tournament_session import TournamentSession


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


class Registry:
    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self.games: dict[str, GameSession] = {}
        self.replays: dict[str, ReplaySession] = {}
        self.tournaments: dict[str, TournamentSession] = {}
        self.limiter = RateLimiter(settings.create_rate_per_minute)
        self._lock = threading.Lock()

    def fresh_id(self, pool: dict[str, Any]) -> str:
        while True:
            i = new_id()
            if i not in pool:
                return i

    def _active(self) -> int:
        return sum(1 for g in self.games.values() if not g.gm.finished and not g.stopping)

    def add_game(self, make: Any) -> GameSession:
        with self._lock:
            self.gc()
            if self._active() >= self.settings.max_concurrent_games:
                self.gc(idle_human=30.0)  # reclaim games whose browser left >30 s ago before refusing
            if self._active() >= self.settings.max_concurrent_games:
                raise RuntimeError("too many concurrent games")
            gid = self.fresh_id(self.games)
            g: GameSession = make(gid)
            self.games[gid] = g
        g.start()
        return g

    def add_tournament(self, make: Any) -> TournamentSession:
        with self._lock:
            if sum(1 for t in self.tournaments.values() if t.status == "running") >= self.settings.max_concurrent_tournaments:
                raise RuntimeError("too many concurrent tournaments")
            tid = self.fresh_id(self.tournaments)
            t: TournamentSession = make(tid)
            self.tournaments[tid] = t
        t.start()
        return t

    def open_replay(self, path: Path) -> ReplaySession:
        with self._lock:
            for r in self.replays.values():
                if r.path == path:
                    return r
            rid = self.fresh_id(self.replays)
            r = ReplaySession(rid, path)
            self.replays[rid] = r
            return r

    def gc(self, max_age: float = 6 * 3600, idle_human: float | None = None) -> None:
        """Drop finished/stopped games older than max_age (their replays/checkpoints are on disk) and checkpoint+stop
        games that wait on a human nobody is watching (`idle_human` seconds without subscribers; default from settings)."""
        now = time.time()
        idle = self.settings.idle_human_timeout if idle_human is None else idle_human
        for gid, g in list(self.games.items()):
            if (g.gm.finished or g.stopping) and now - g.created > max_age:
                del self.games[gid]
            elif not g.gm.finished and not g.stopping and (g.pending is not None or g.waiting_for()) and g.idle_since is not None and now - g.idle_since > idle:
                try:
                    g.stop(save=True)  # abandoned browser tab: keep the game resumable, free the slot
                except Exception:
                    g.stop(save=False)

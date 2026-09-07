"""Server settings (env `CLUE_WEB_*` or constructor)."""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLUE_WEB_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    secret: str = ""  # HMAC salt for per-game tokens; random per process when empty
    replay_dir: Path = Path("replays")
    saves_dir: Path = Path("saves")
    hotseat: bool = False  # allow several human seats in one browser (pass-the-device)
    remote: bool = True  # allow several human seats in different browsers (one invite link per seat)
    max_concurrent_games: int = 8
    idle_human_timeout: float = 600.0  # seconds a game may wait on a human with no browser connected before it is checkpointed and stopped
    max_concurrent_tournaments: int = 2
    create_rate_per_minute: int = 20  # per client IP, for POST /games and /tournaments
    dev_origin: str | None = None  # e.g. http://localhost:5173 for `npm run dev`
    static_dir: Path = Path(__file__).parent / "static"

    def model_post_init(self, __context: object) -> None:
        if not self.secret:
            object.__setattr__(self, "secret", secrets.token_hex(16))

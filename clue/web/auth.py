"""Per-game secret links (LAN-level protection, no accounts): token = hmac(secret, id:role)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def new_id(n: int = 6) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes
    return "".join(secrets.choice(alphabet) for _ in range(n))


def token(secret: str, sid: str, role: str) -> str:
    return hmac.new(secret.encode(), f"{sid}:{role}".encode(), hashlib.sha256).hexdigest()[:24]


def seat_role(pid: str) -> str:
    return f"seat:{pid}"


def role_of(secret: str, sid: str, tok: str | None, seats: list[str] | None = None) -> str | None:
    """'owner' | 'spectator' | 'seat:<pid>' (remote human seat) | None (invalid)."""
    if not tok:
        return None
    for role in ["owner", "spectator", *(seat_role(p) for p in seats or [])]:
        if hmac.compare_digest(token(secret, sid, role), tok):
            return role
    return None

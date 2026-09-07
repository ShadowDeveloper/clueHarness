from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from clue.web.deps import registry, settings
from clue.web.schemas import OpenReplay, ReplayInfo
from clue.web.sessions import Registry
from clue.web.settings import WebSettings

router = APIRouter()


@router.get("/replays")
def list_replays(st: WebSettings = Depends(settings)) -> list[dict[str, Any]]:
    out = []
    if st.replay_dir.exists():
        for p in sorted(st.replay_dir.iterdir(), key=lambda p: -p.stat().st_mtime):
            if p.suffix in (".jsonl", ".json"):
                out.append({"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime, "redacted": "_redacted_" in p.name})
    return out


@router.post("/replays/open", response_model=ReplayInfo)
def open_replay(body: OpenReplay, reg: Registry = Depends(registry), st: WebSettings = Depends(settings)) -> ReplayInfo:
    path = (st.replay_dir / body.name).resolve()
    if path.parent != st.replay_dir.resolve() or not path.exists():
        raise HTTPException(404, "replay not found")
    try:
        r = reg.open_replay(path)
    except Exception as e:
        raise HTTPException(422, f"cannot parse replay: {e}") from e
    return ReplayInfo(**r.info())


@router.get("/replays/{replay_id}/frames")
def frames(replay_id: str, viewer: str | None = None, reg: Registry = Depends(registry)) -> dict[str, Any]:
    r = reg.replays.get(replay_id)
    if r is None:
        raise HTTPException(404, "replay not opened")
    if viewer == "__omni__" and not r.omniscient:
        raise HTTPException(403, "this replay file is redacted; no omniscient view")
    if viewer not in (None, "__omni__") and viewer not in [p["id"] for p in r.state.players]:
        raise HTTPException(404, "unknown viewer")
    return r.frames(viewer)

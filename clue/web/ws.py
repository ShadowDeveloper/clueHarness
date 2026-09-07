"""WebSocket push channels. Game threads call subscriber callbacks synchronously; we hop onto the event loop with
`loop.call_soon_threadsafe` into a bounded asyncio.Queue, and one task drains it to the socket."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from clue.web.auth import role_of
from clue.web.deps import resolve_viewer
from clue.web.sessions import Registry
from clue.web.settings import WebSettings

router = APIRouter()


class _Bridge:
    def __init__(self, loop: asyncio.AbstractEventLoop, maxsize: int = 1000) -> None:
        self.loop = loop
        self.q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=maxsize)

    def __call__(self, frame: dict[str, Any]) -> None:  # from any thread
        def _put() -> None:
            if self.q.full():
                try:
                    self.q.get_nowait()  # drop the oldest; the client can re-sync from /games/{id}
                except asyncio.QueueEmpty:
                    pass
            self.q.put_nowait(frame)

        self.loop.call_soon_threadsafe(_put)


async def _pump(ws: WebSocket, bridge: _Bridge) -> None:
    """Send frames until the client disconnects. Client messages are only pings."""

    async def reader() -> None:
        try:
            while True:
                msg = await ws.receive_text()
                if msg == '{"type":"ping"}' or msg == "ping":
                    await ws.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            pass
        finally:
            bridge.loop.call_soon_threadsafe(lambda: bridge.q.put_nowait(None))

    rt = asyncio.create_task(reader())
    try:
        while True:
            frame = await bridge.q.get()
            if frame is None:
                break
            await ws.send_text(json.dumps(frame, default=str))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        rt.cancel()


@router.websocket("/ws/games/{game_id}")
async def game_ws(ws: WebSocket, game_id: str, k: str | None = None, view: str | None = None) -> None:
    reg: Registry = ws.app.state.registry
    st: WebSettings = ws.app.state.settings
    sess = reg.games.get(game_id)
    role = role_of(st.secret, game_id, k, sess.humans if sess.remote else None) if sess else None
    if sess is None or role is None:
        await ws.close(code=4403)
        return
    viewer = resolve_viewer(sess, role, view)
    await ws.accept()
    bridge = _Bridge(asyncio.get_running_loop())
    sub = sess.subscribe(viewer, bridge)
    try:
        await ws.send_text(json.dumps(sess.render_frame(viewer), default=str))
        await _pump(ws, bridge)
    finally:
        sess.unsubscribe(sub)


@router.websocket("/ws/tournaments/{tid}")
async def tournament_ws(ws: WebSocket, tid: str) -> None:
    reg: Registry = ws.app.state.registry
    t = reg.tournaments.get(tid)
    if t is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    bridge = _Bridge(asyncio.get_running_loop())
    sub = t.subscribe(bridge)
    try:
        await ws.send_text(json.dumps({"type": "snapshot", **t.snapshot()}, default=str))
        await _pump(ws, bridge)
    finally:
        t.unsubscribe(sub)

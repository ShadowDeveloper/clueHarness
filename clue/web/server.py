"""FastAPI app factory + `serve()` entry point used by `clue web`."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from clue.web import ws
from clue.web.routes import analyze, games, meta, replays, tournaments
from clue.web.sessions import Registry
from clue.web.settings import WebSettings


def create_app(settings: WebSettings | None = None) -> FastAPI:
    st = settings or WebSettings()
    app = FastAPI(title="Clue harness", version="1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = st
    app.state.registry = Registry(st)
    if st.dev_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[st.dev_origin], allow_methods=["*"], allow_headers=["*"])
    for r in (meta.router, games.router, replays.router, tournaments.router, analyze.router):
        app.include_router(r, prefix="/api")
    app.include_router(ws.router)

    static = Path(st.static_dir)
    index = static / "index.html"
    if (static / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> Response:
        if full_path.startswith(("api/", "ws/")):
            return JSONResponse({"detail": "not found"}, status_code=404)
        f = static / full_path
        if full_path and f.is_file() and f.resolve().is_relative_to(static.resolve()):
            return FileResponse(f)
        if index.exists():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return JSONResponse({"detail": "frontend bundle not built; run `npm run build` in web/ (API is at /api/docs)"}, status_code=503)

    return app


def serve(settings: WebSettings | None = None, open_browser: bool = False) -> None:
    import uvicorn

    st = settings or WebSettings()
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{st.port}/")).start()
    uvicorn.run(create_app(st), host=st.host, port=st.port, log_level="info")

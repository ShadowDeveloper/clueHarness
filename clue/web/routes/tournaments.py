from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from clue.agents.factory import parse_players_arg
from clue.agents.llm_client import configure_budget
from clue.eval.tournament import markdown_table
from clue.rules.cards import max_players
from clue.web.deps import registry
from clue.web.schemas import CreateTournament, TournamentStatus
from clue.web.sessions import Registry
from clue.web.tournament_session import TournamentSession

router = APIRouter()


@router.post("/tournaments", response_model=TournamentStatus, status_code=201)
def create(body: CreateTournament, request: Request, reg: Registry = Depends(registry)) -> dict[str, Any]:
    if not reg.limiter.allow(request.client.host if request.client else "?"):
        raise HTTPException(429, "slow down")
    if body.players:
        specs = body.players
    elif body.players_arg:
        try:
            specs = parse_players_arg(body.players_arg)
        except Exception as e:
            raise HTTPException(422, str(e)) from e
    else:
        raise HTTPException(422, "players or players_arg required")
    if any(s.kind == "human" for s in specs):
        raise HTTPException(422, "tournaments are AI-only")
    edition = body.config.edition if body.config else "classic"
    if not 3 <= len(specs) <= max_players(edition):
        raise HTTPException(422, f"{edition} edition: 3-{max_players(edition)} players")
    if body.max_usd is not None:
        configure_budget(body.max_usd)
    try:
        t = reg.add_tournament(lambda tid: TournamentSession(tid, specs, body.games, body.seed, body.workers, body.ponder, body.provider, body.config, body.probe, body.duplicate))
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return t.snapshot()


@router.get("/tournaments")
def list_tournaments(reg: Registry = Depends(registry)) -> list[dict[str, Any]]:
    return [{k: v for k, v in t.snapshot().items() if k != "report"} for t in reg.tournaments.values()]


def _get(reg: Registry, tid: str) -> TournamentSession:
    t = reg.tournaments.get(tid)
    if t is None:
        raise HTTPException(404, "tournament not found")
    return t


@router.get("/tournaments/{tid}", response_model=TournamentStatus)
def status(tid: str, reg: Registry = Depends(registry)) -> dict[str, Any]:
    return _get(reg, tid).snapshot()


@router.delete("/tournaments/{tid}")
def cancel(tid: str, reg: Registry = Depends(registry)) -> dict[str, Any]:
    t = _get(reg, tid)
    t.cancel()
    return {"ok": True, "status": t.status}


@router.get("/tournaments/{tid}/report.{fmt}")
def report(tid: str, fmt: str, reg: Registry = Depends(registry)) -> Response:
    rep = _get(reg, tid).current_report()
    if rep is None:
        raise HTTPException(409, "no games finished yet")
    if fmt == "json":
        return Response(json.dumps(rep, indent=1), media_type="application/json")
    if fmt == "md":
        return PlainTextResponse(markdown_table(rep), media_type="text/markdown")
    if fmt == "csv":
        buf = io.StringIO()
        rows = [{k: (f"{v[0]}-{v[1]}" if isinstance(v, list) else v) for k, v in r.items()} for r in rep["table"]]
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    raise HTTPException(404, "format must be json, md or csv")

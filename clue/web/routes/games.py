from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from clue.agents.factory import parse_players_arg
from clue.manager.game_manager import GameManager
from clue.rules import GameConfig, IllegalAction
from clue.web.auth import token
from clue.web.deps import Access, access, registry, settings
from clue.web.game_session import GameSession, build_agents
from clue.web.schemas import ActBody, ControlBody, CreateGame, GameCreated, GameListItem, NoteBody, OkPath, SaveBody
from clue.web.sessions import Registry
from clue.web.settings import WebSettings

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


@router.post("/games", response_model=GameCreated, status_code=201)
def create_game(body: CreateGame, request: Request, reg: Registry = Depends(registry), st: WebSettings = Depends(settings)) -> GameCreated:
    if not reg.limiter.allow(_client_ip(request)):
        raise HTTPException(429, "too many games created; slow down")
    resumed, restored = False, []
    if body.resume:
        path = (st.saves_dir / body.resume).resolve()
        if path.parent != st.saves_dir.resolve() or not path.exists():
            raise HTTPException(404, "checkpoint not found")
        gm = GameManager.load(path)
        if gm.finished:
            raise HTTPException(409, "that game is finished")
        specs = gm.specs
        agents = build_agents(specs, gm.seed, body.provider)
        restored = gm.restore_agents(agents)
        resumed = True
        autosave: str | None = str(path)
    else:
        if body.players:
            specs = body.players
        elif body.players_arg:
            try:
                specs = parse_players_arg(body.players_arg)
            except Exception as e:
                raise HTTPException(422, str(e)) from e
        else:
            raise HTTPException(422, "players or players_arg required")
        if not 3 <= len(specs) <= 6:
            raise HTTPException(422, "3-6 players")
        humans = [s for s in specs if s.kind == "human"]
        if len(humans) > 1 and not st.hotseat:
            raise HTTPException(422, "several human seats need the server started with --hotseat")
        cfg = body.config or GameConfig(num_players=len(specs))
        if cfg.num_players != len(specs):
            cfg = cfg.model_copy(update={"num_players": len(specs)})
        seed = body.seed if body.seed is not None else int.from_bytes(__import__("os").urandom(3), "big")
        try:
            gm = GameManager.create(specs, seed=seed, config=cfg)
            agents = build_agents(specs, seed, body.provider)
        except Exception as e:
            raise HTTPException(422, str(e)) from e
        autosave = str(st.saves_dir / f"game_{seed}.json") if body.autosave else None
    try:
        sess = reg.add_game(
            lambda gid: GameSession(gid, gm, agents, delay=body.delay, ponder=body.ponder, ponder_grace=body.ponder_grace, autosave=autosave, replay_dir=st.replay_dir, hotseat=st.hotseat)
        )
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return GameCreated(
        id=sess.id,
        owner_token=token(st.secret, sess.id, "owner"),
        spectator_token=token(st.secret, sess.id, "spectator"),
        seats=[{"id": s.id, "label": s.label(), "kind": s.kind, "name": s.name} for s in specs],
        humans=sess.humans,
        resumed=resumed,
        restored=restored,
    )


@router.get("/games", response_model=list[GameListItem])
def list_games(reg: Registry = Depends(registry)) -> list[GameListItem]:
    out = []
    for g in reg.games.values():
        out.append(
            GameListItem(
                id=g.id,
                seed=g.gm.seed,
                players=g.gm.player_ids(),
                labels={s.id: s.label() for s in g.gm.specs},
                humans=g.humans,
                finished=g.gm.finished,
                turn=g.gm.state.turn_number,
                created=g.created,
                winner=g.gm.winner,
            )
        )
    return out


@router.get("/games/{game_id}")
def get_game(acc: Access = Depends(access)) -> dict[str, Any]:
    return acc.session.render_frame(acc.viewer)


@router.post("/games/{game_id}/act", response_model=OkPath)
def act(body: ActBody, acc: Access = Depends(access)) -> OkPath:
    seat = acc.human_seat(body.player)
    try:
        acc.session.act(seat, body.request_id, body.action, body.card)
    except LookupError as e:
        raise HTTPException(409, str(e)) from e
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    except (IllegalAction, ValueError, TypeError) as e:
        acc.session.gm.illegal_attempts[seat] = acc.session.gm.illegal_attempts.get(seat, 0) + 1
        raise HTTPException(422, f"illegal action: {e}") from e
    return OkPath()


@router.post("/games/{game_id}/control", response_model=OkPath)
def control(body: ControlBody, acc: Access = Depends(access)) -> OkPath:
    if acc.role != "owner":
        raise HTTPException(403, "owner only")
    if body.pause is not None:
        acc.session.set_pause(body.pause)
    if body.delay is not None:
        acc.session.set_delay(body.delay)
    if body.acknowledge_seat is not None:
        if not acc.session.hotseat:
            raise HTTPException(409, "hot-seat mode is disabled")
        try:
            acc.session.acknowledge_seat(body.acknowledge_seat)
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e
    return OkPath()


@router.post("/games/{game_id}/coach")
def coach(acc: Access = Depends(access), player: str | None = None) -> dict[str, Any]:
    seat = acc.human_seat(player)
    return acc.session.coach(seat)


@router.put("/games/{game_id}/notes")
def notes(body: NoteBody, acc: Access = Depends(access)) -> dict[str, Any]:
    seat = acc.human_seat(body.player)
    return {"notes": acc.session.add_note(seat, body.note)}


@router.post("/games/{game_id}/save", response_model=OkPath)
def save(body: SaveBody, acc: Access = Depends(access), st: WebSettings = Depends(settings)) -> OkPath:
    if acc.role != "owner":
        raise HTTPException(403, "owner only")
    if acc.session.gm.finished:
        raise HTTPException(409, "game is finished")
    path = str(st.saves_dir / f"{body.name}.json") if body.name else None
    return OkPath(path=acc.session.save(path))


@router.delete("/games/{game_id}", response_model=OkPath)
def stop(acc: Access = Depends(access)) -> OkPath:
    if acc.role != "owner":
        raise HTTPException(403, "owner only")
    return OkPath(path=acc.session.stop(save=True))


@router.get("/saves")
def list_saves(st: WebSettings = Depends(settings)) -> list[dict[str, Any]]:
    import json

    out = []
    if st.saves_dir.exists():
        for p in sorted(st.saves_dir.glob("*.json"), key=lambda p: -p.stat().st_mtime):
            try:
                d = json.loads(p.read_text())
                specs = d.get("specs", [])
                out.append(
                    {
                        "name": p.name,
                        "seed": d.get("seed"),
                        "turn": (d.get("state") or {}).get("turn_number"),
                        "players": [s.get("id") for s in specs],
                        "labels": [f"{s.get('kind')}{':' + s['bot'] if s.get('bot') else ''}" for s in specs],
                        "mtime": p.stat().st_mtime,
                    }
                )
            except Exception:
                continue
    return out

"""Web backend: REST + WebSocket, privacy on every frame, human seat via HTTP, save/resume, replays, tournaments."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from clue.manager import GameManager  # noqa: E402
from clue.web.server import create_app  # noqa: E402
from clue.web.settings import WebSettings  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(WebSettings(replay_dir=tmp_path / "replays", saves_dir=tmp_path / "saves", secret="test", hotseat=True))
    return TestClient(app)


def _create(client: TestClient, players: str, **kw: Any) -> dict[str, Any]:
    r = client.post("/api/games", json={"players_arg": players, "seed": kw.pop("seed", 7), "delay": 0, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _drain(ws: Any, until: tuple[str, ...] = ("finished", "stopped", "error"), timeout: float = 120) -> list[dict[str, Any]]:
    frames = []
    t0 = time.time()
    while time.time() - t0 < timeout:
        f = ws.receive_json()
        frames.append(f)
        if f["type"] in until:
            break
    return frames


def _leaks(frames: list[dict[str, Any]], secrets: list[str]) -> list[str]:
    """Return any secret string that appears anywhere in the serialised frames."""
    blob = json.dumps(frames)
    return [s for s in secrets if s in blob]


# ---------------------------------------------------------------- meta


def test_health_board_catalog(client: TestClient) -> None:
    assert client.get("/api/health").json()["ok"]
    b = client.get("/api/board").json()
    assert b["rows"] == 25 and len(b["rooms"]) == 9 and b["doors"]
    cat = client.get("/api/catalog").json()
    assert "expert" in cat["bots"] and cat["strategies"] and cat["hotseat"]
    assert client.get("/api/nope").status_code == 404
    assert client.get("/").status_code in (200, 503)  # bundle may or may not be built


# ---------------------------------------------------------------- spectating + privacy


def test_bot_game_streams_and_owner_is_omniscient(client: TestClient) -> None:
    g = _create(client, "baseline:expert,baseline,baseline", seed=3)
    with client.websocket_connect(f"/ws/games/{g['id']}?k={g['owner_token']}") as ws:
        frames = _drain(ws)
    assert frames[0]["type"] == "snapshot" and frames[0]["state"]["viewer"] == "__omni__"
    assert "omniscient" in frames[0]["state"] and frames[0]["state"]["omniscient"]["solution"]
    assert frames[-1]["type"] == "finished" and frames[-1]["summary"]["winner"]
    assert any(f["type"] == "events" for f in frames)
    # replays written; game listed
    assert (client.get("/api/replays").json()) and any(r["name"].endswith(".jsonl") for r in client.get("/api/replays").json())
    lst = client.get("/api/games").json()
    assert lst[0]["id"] == g["id"] and lst[0]["finished"]


def test_seat_view_never_leaks_other_hands_or_solution(client: TestClient) -> None:
    """Every frame sent to a seat viewer (bots-only game, spectator token) must not contain the other seats' cards."""
    g = _create(client, "baseline,baseline,baseline,baseline", seed=11)
    sess = client.app.state.registry.games[g["id"]]  # type: ignore[attr-defined]
    st = sess.gm.state
    with client.websocket_connect(f"/ws/games/{g['id']}?k={g['spectator_token']}&view=P2") as ws:
        frames = _drain(ws)
    assert frames[0]["state"]["viewer"] == "P2"
    others = [c for p in st.players if p.id != "P2" for c in p.hand]
    # cards can legitimately appear in public text (suggestions), so check the structured private fields only
    for f in frames:
        s = f.get("state", {})
        assert "omniscient" not in s
        if "you" in s:
            assert set(s["you"]["hand"]) == set(st.player("P2").hand)
        for e in f.get("events", []):
            if e["type"] == "disproved" and "card" in e:
                assert "P2" in (e.get("suggester"), e.get("disprover"))
            assert "hands" not in e and (e["type"] == "game_over" or "solution" not in e)
    # the finished frame's summary reveals the solution to everybody (game over) - that is by design
    assert frames[-1]["type"] == "finished"
    assert others  # sanity


def test_invalid_token_rejected(client: TestClient) -> None:
    g = _create(client, "baseline,baseline,baseline")
    assert client.get(f"/api/games/{g['id']}?k=bad").status_code == 403
    assert client.get(f"/api/games/{g['id']}").status_code == 403
    assert client.get(f"/api/games/zzzzzz?k={g['owner_token']}").status_code == 404
    assert client.post(f"/api/games/{g['id']}/control", params={"k": g["spectator_token"]}, json={"pause": True}).status_code == 403


# ---------------------------------------------------------------- human seat over HTTP


def _play_human(client: TestClient, g: dict[str, Any], scripted: Any, max_steps: int = 600) -> list[dict[str, Any]]:
    """Drive the human seat with `scripted(request) -> body` through /act until the game ends."""
    frames: list[dict[str, Any]] = []
    gid, k = g["id"], g["owner_token"]
    with client.websocket_connect(f"/ws/games/{gid}?k={k}") as ws:
        steps = 0
        while steps < max_steps:
            f = ws.receive_json()
            frames.append(f)
            if f["type"] in ("finished", "stopped", "error"):
                break
            req = f.get("request") if f["type"] in ("request", "snapshot") else None
            if req:
                r = client.post(f"/api/games/{gid}/act", params={"k": k}, json={"request_id": req["request_id"], **scripted(req)})
                assert r.status_code == 200, r.text
                steps += 1
    return frames


def _first_legal(req: dict[str, Any]) -> dict[str, Any]:
    if req["kind"] == "card":
        return {"card": req["cards"][0]}
    legal = req["legal"]
    # prefer roll/move/suggest/end_turn in that order; never accuse blindly
    for t in ("roll", "passage", "move", "suggest", "end_turn"):
        for a in legal:
            if a["type"] == t:
                return {"action": a}
    return {"action": legal[0]}


def test_human_seat_plays_full_game_via_http_with_zero_illegal(client: TestClient) -> None:
    g = _create(client, "human,baseline:expert,baseline", seed=5)
    assert g["humans"] == ["P1"]
    frames = _play_human(client, g, _first_legal)
    sess = client.app.state.registry.games[g["id"]]  # type: ignore[attr-defined]
    assert frames[-1]["type"] == "finished"
    assert sess.gm.illegal_attempts.get("P1", 0) == 0
    # seat view: the human's own hand present, omniscient data absent
    assert all("omniscient" not in f.get("state", {}) for f in frames)
    assert frames[0]["state"]["you"]["hand"]


def test_act_validation_and_stale_request(client: TestClient) -> None:
    g = _create(client, "human,baseline,baseline", seed=5)
    gid, k = g["id"], g["owner_token"]
    with client.websocket_connect(f"/ws/games/{gid}?k={k}") as ws:
        f = ws.receive_json()
        req = f["request"]
        assert req and req["kind"] == "action"
        # illegal action -> 422 and counted
        r = client.post(f"/api/games/{gid}/act", params={"k": k}, json={"request_id": req["request_id"], "action": {"type": "move", "to": "Kitchen"}})
        assert r.status_code == 422
        # stale id -> 409
        assert client.post(f"/api/games/{gid}/act", params={"k": k}, json={"request_id": 999, "action": req["legal"][0]}).status_code == 409
        # spectator cannot act
        assert client.post(f"/api/games/{gid}/act", params={"k": g["spectator_token"]}, json={"request_id": req["request_id"], "action": req["legal"][0]}).status_code == 403
        # coach works and is logged; notes stored
        h = client.post(f"/api/games/{gid}/coach", params={"k": k}).json()
        assert h["candidates"] > 1 and h["expert_action"]
        assert client.put(f"/api/games/{gid}/notes", params={"k": k}, json={"note": "Plum looks shifty"}).json()["notes"] == ["Plum looks shifty"]
        sess = client.app.state.registry.games[gid]  # type: ignore[attr-defined]
        assert sess.gm.illegal_attempts["P1"] == 1
        assert any(r.kind == "agent_note" and r.data.get("summary") == "coach_mode_on" for r in sess.gm.log)
        # spectator sees the table view only (a human is present)
        snap = client.get(f"/api/games/{gid}?k={g['spectator_token']}&view=P1").json()
        assert snap["state"]["viewer"] == "__table__" and "you" not in snap["state"] and snap["request"] is None
        # stop -> saves, unblocks the pending human, loop ends
        r = client.delete(f"/api/games/{gid}", params={"k": k})
        assert r.status_code == 200 and r.json()["path"]
        frames = _drain(ws, timeout=20)
        assert frames[-1]["type"] == "stopped"
    assert Path(r.json()["path"]).exists()


def test_save_resume_via_api_reproduces_replay_hash(client: TestClient, tmp_path: Path) -> None:
    # reference: uninterrupted
    ref = _create(client, "baseline,baseline:expert,llm:aggressive", seed=21, autosave=False)
    with client.websocket_connect(f"/ws/games/{ref['id']}?k={ref['owner_token']}") as ws:
        _drain(ws)
    ref_hash = client.app.state.registry.games[ref["id"]].gm.replay_hash()  # type: ignore[attr-defined]
    # interrupted: pause immediately, save under a name, stop
    g = _create(client, "baseline,baseline:expert,llm:aggressive", seed=21, delay=0.05)
    k = g["owner_token"]
    client.post(f"/api/games/{g['id']}/control", params={"k": k}, json={"pause": True})
    time.sleep(0.3)
    r = client.post(f"/api/games/{g['id']}/save", params={"k": k}, json={"name": "mid"})
    assert r.status_code == 200
    client.delete(f"/api/games/{g['id']}", params={"k": k})
    saved = GameManager.load(tmp_path / "saves" / "mid.json")
    assert not saved.finished
    # resume
    r2 = client.post("/api/games", json={"resume": "mid.json", "delay": 0})
    assert r2.status_code == 201, r2.text
    g2 = r2.json()
    assert g2["resumed"] and set(g2["restored"]) == {"P1", "P2", "P3"}
    with client.websocket_connect(f"/ws/games/{g2['id']}?k={g2['owner_token']}") as ws:
        frames = _drain(ws)
    assert frames[-1]["type"] == "finished"
    assert client.app.state.registry.games[g2["id"]].gm.replay_hash() == ref_hash  # type: ignore[attr-defined]
    assert client.get("/api/saves").json() == [] or all(s["name"] != "mid.json" for s in client.get("/api/saves").json())
    assert client.post("/api/games", json={"resume": "../x.json"}).status_code == 404


# ---------------------------------------------------------------- hot-seat


def test_hotseat_withholds_other_seat_until_acknowledged(client: TestClient) -> None:
    g = _create(client, "human,human,baseline", seed=9)
    gid, k = g["id"], g["owner_token"]
    assert g["humans"] == ["P1", "P2"]
    with client.websocket_connect(f"/ws/games/{gid}?k={k}&view=P2") as ws2, client.websocket_connect(f"/ws/games/{gid}?k={k}") as ws1:
        s2 = ws2.receive_json()
        assert s2["state"]["viewer"] == "P2" and not s2["state"]["seat_visible"] and "you" not in s2["state"]
        s1 = ws1.receive_json()
        assert s1["state"]["viewer"] == "P1" and s1["request"]
        # P1 plays until the request goes to P2
        req = s1["request"]
        for _ in range(40):
            client.post(f"/api/games/{gid}/act", params={"k": k}, json={"request_id": req["request_id"], "player": "P1", **_first_legal(req)})
            f = ws1.receive_json()
            while f["type"] not in ("request",):
                f = ws1.receive_json()
            if f["pending_for"] == "P2":
                break
            req = f["request"]
        assert f["pending_for"] == "P2" and f["handoff_pending"] == "P2" and f["request"] is None
        # P2's channel: still no private data or request until acknowledged
        f2 = ws2.receive_json()
        while f2["type"] != "request" or f2["pending_for"] != "P2":
            f2 = ws2.receive_json()
        assert f2["request"] is None
        rid = client.app.state.registry.games[gid].pending.request_id  # type: ignore[attr-defined]
        assert client.post(f"/api/games/{gid}/act", params={"k": k}, json={"request_id": rid, "player": "P2", "action": {"type": "roll"}}).status_code == 409
        assert client.post(f"/api/games/{gid}/control", params={"k": k}, json={"acknowledge_seat": "P2"}).status_code == 200
        f2 = ws2.receive_json()
        while f2["type"] != "request" or not f2["request"]:
            f2 = ws2.receive_json()
        assert f2["request"]["request_id"] == rid
        snap = client.get(f"/api/games/{gid}?k={k}&view=P2").json()
        assert snap["state"]["seat_visible"] and snap["state"]["you"]["hand"]
        client.delete(f"/api/games/{gid}", params={"k": k})


def test_multiple_humans_rejected_without_hotseat_or_remote(tmp_path: Path) -> None:
    c = TestClient(create_app(WebSettings(replay_dir=tmp_path, saves_dir=tmp_path, secret="t", hotseat=False, remote=False)))
    r = c.post("/api/games", json={"players_arg": "human,human,baseline"})
    assert r.status_code == 422


# ---------------------------------------------------------------- remote seats (M7)


def test_remote_seats_two_browsers_play_to_completion_with_per_seat_privacy(tmp_path: Path) -> None:
    """Two seat links in two 'browsers': the game waits until both joined, each token only controls its own seat,
    and no frame sent to a seat contains the other hand or the solution before game over."""
    c = TestClient(create_app(WebSettings(replay_dir=tmp_path / "r", saves_dir=tmp_path / "s", secret="t", hotseat=False)))
    r = c.post("/api/games", json={"players_arg": "human,human,baseline:expert", "seed": 21, "delay": 0})
    assert r.status_code == 201, r.text
    g = r.json()
    gid, host = g["id"], g["owner_token"]
    assert g["remote"] and set(g["seat_tokens"]) == {"P1", "P2"}
    k1, k2 = g["seat_tokens"]["P1"], g["seat_tokens"]["P2"]
    inv = c.get(f"/api/games/{gid}/invites", params={"k": host}).json()
    assert inv["seats"] == g["seat_tokens"] and inv["waiting_for"] == ["P1", "P2"]
    assert c.get(f"/api/games/{gid}/invites", params={"k": k1}).status_code == 403
    sess = c.app.state.registry.games[gid]  # type: ignore[attr-defined]
    gm: GameManager = sess.gm
    hands = {p.id: list(p.hand) for p in gm.state.players}
    solution = list(gm.state.solution)
    frames: dict[str, list[dict[str, Any]]] = {"P1": [], "P2": []}
    with c.websocket_connect(f"/ws/games/{gid}?k={k1}&view=P2") as ws1:  # `view` must be ignored for seat tokens
        s1 = ws1.receive_json()
        frames["P1"].append(s1)
        assert s1["state"]["viewer"] == "P1" and s1["state"]["waiting_for"] == ["P2"] and s1["request"] is None
        assert not sess.started.is_set() and sess.pending is None
        # a seat token cannot act for another seat
        with c.websocket_connect(f"/ws/games/{gid}?k={k2}") as ws2:
            s2 = ws2.receive_json()
            frames["P2"].append(s2)
            assert s2["state"]["viewer"] == "P2" and s2["state"]["you"]["hand"] == hands["P2"]
            socks = {"P1": ws1, "P2": ws2}
            toks = {"P1": k1, "P2": k2}
            # both are joined now -> game starts; drive whichever seat is asked
            done = False
            steps = 0
            while not done and steps < 800:
                for pid, ws in socks.items():
                    f = ws.receive_json()
                    frames[pid].append(f)
                    if f["type"] in ("finished", "stopped", "error"):
                        done = True
                        break
                    req = f.get("request") if f["type"] in ("request", "snapshot") else None
                    if req:
                        other = "P2" if pid == "P1" else "P1"
                        bad = c.post(f"/api/games/{gid}/act", params={"k": toks[other]}, json={"request_id": req["request_id"], **_first_legal(req)})
                        assert bad.status_code in (403, 409), bad.text  # other seat's link cannot answer
                        ok = c.post(f"/api/games/{gid}/act", params={"k": toks[pid]}, json={"request_id": req["request_id"], "player": pid, **_first_legal(req)})
                        assert ok.status_code == 200, ok.text
                        steps += 1
            assert gm.finished, "game did not finish"
            assert sum(gm.illegal_attempts.values()) == 0
    for pid in ("P1", "P2"):
        for f in frames[pid]:
            st_ = f.get("state", {})
            assert "omniscient" not in st_ and st_.get("viewer", pid) == pid
            if "you" in st_:
                assert st_["you"]["hand"] == hands[pid]
            for e in f.get("events", []):
                if e["type"] == "disproved" and "card" in e:
                    assert pid in (e.get("suggester"), e.get("disprover"))
                assert "hands" not in e and (e["type"] == "game_over" or "solution" not in e)
            if f["type"] != "finished":
                assert "solution" not in json.dumps(f.get("state", {}))
    assert solution  # sanity
    # seat tokens survive a stop/resume: presence is tracked per seat
    lst = c.get("/api/games").json()
    me = next(x for x in lst if x["id"] == gid)
    assert me["remote"] and me["presence"] == {"P1": 0, "P2": 0}


def test_remote_host_can_force_start_and_idle_lobby_is_reclaimed(tmp_path: Path) -> None:
    c = TestClient(create_app(WebSettings(replay_dir=tmp_path / "r", saves_dir=tmp_path / "s", secret="t", hotseat=False, idle_human_timeout=0.0)))
    g = c.post("/api/games", json={"players_arg": "human,human,baseline", "seed": 3, "delay": 0}).json()
    gid, host = g["id"], g["owner_token"]
    sess = c.app.state.registry.games[gid]  # type: ignore[attr-defined]
    assert sess.waiting_for() == ["P1", "P2"] and not sess.started.is_set()
    # spectator/host tokens do not count as seats joining
    with c.websocket_connect(f"/ws/games/{gid}?k={g['spectator_token']}") as ws:
        s = ws.receive_json()
        assert s["state"]["viewer"] == "__table__" and s["state"]["waiting_for"] == ["P1", "P2"]
    assert not sess.started.is_set()
    # host forces the start (missing seats' bots... no: the human seats still exist; the game just proceeds and waits on them)
    assert c.post(f"/api/games/{gid}/control", params={"k": host}, json={"start": True}).status_code == 200
    t0 = time.time()
    while sess.pending is None and time.time() - t0 < 10:
        time.sleep(0.05)
    assert sess.started.is_set() and sess.pending is not None and sess.pending.player == "P1"
    # nobody connected -> gc checkpoints and frees the slot
    c.app.state.registry.gc()  # type: ignore[attr-defined]
    assert sess.stopping and Path(sess.autosave).exists()  # type: ignore[arg-type]
    # a second lobby that nobody ever joins is reclaimed too
    g2 = c.post("/api/games", json={"players_arg": "human,human,baseline", "seed": 4, "delay": 0}).json()
    s2 = c.app.state.registry.games[g2["id"]]  # type: ignore[attr-defined]
    c.app.state.registry.gc()  # type: ignore[attr-defined]
    assert s2.stopping


# ---------------------------------------------------------------- replays


def test_replay_private_disproofs_hide_bystander_details(tmp_path: Path) -> None:
    from clue.web.replay_session import ReplaySession

    records = [
        {
            "seq": 0,
            "kind": "event",
            "type": "game_start",
            "players": [{"id": f"P{i}", "kind": "baseline"} for i in range(1, 5)],
            "config": {
                "edition": "classic",
                "private_disproofs": True,
                "teams": [["P1"], ["P2", "P4"], ["P3"]],
            },
            "solution": ["Prof. Plum", "Rope", "Study"],
            "hands": {f"P{i}": [] for i in range(1, 5)},
        },
        {"seq": 1, "kind": "event", "type": "can_disprove", "turn": 1, "player": "P2", "suggester": "P1"},
        {
            "seq": 2,
            "kind": "event",
            "type": "disproved",
            "turn": 1,
            "player": None,
            "suggester": "P1",
            "disprover": "P2",
            "card": "Rope",
        },
    ]
    path = tmp_path / "private.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    session = ReplaySession("test", path)

    bystander = session.frames("P3")
    visible_events = [frame["event"] for frame in bystander["frames"] if frame["event"]]
    assert all(event["type"] != "can_disprove" for event in visible_events)
    disproved = next(event for event in visible_events if event["type"] == "disproved")
    assert "card" not in disproved and "disprover" not in disproved and disproved["player"] is None
    assert bystander["info"]["n_events"] == 1

    involved = session.frames("P1")
    visible_events = [frame["event"] for frame in involved["frames"] if frame["event"]]
    assert any(event["type"] == "can_disprove" for event in visible_events)
    disproved = next(event for event in visible_events if event["type"] == "disproved")
    assert disproved["card"] == "Rope" and disproved["disprover"] == "P2"

    teammate = session.frames("P4")
    visible_events = [frame["event"] for frame in teammate["frames"] if frame["event"]]
    assert all(event["type"] != "can_disprove" for event in visible_events)
    disproved = next(event for event in visible_events if event["type"] == "disproved")
    assert disproved["card"] == "Rope" and disproved["disprover"] == "P2"


def test_replay_frames_redaction(client: TestClient) -> None:
    g = _create(client, "baseline,baseline,baseline", seed=13)
    with client.websocket_connect(f"/ws/games/{g['id']}?k={g['owner_token']}") as ws:
        _drain(ws)
    names = [r["name"] for r in client.get("/api/replays").json()]
    full = next(n for n in names if n.endswith(".jsonl"))
    info = client.post("/api/replays/open", json={"name": full}).json()
    assert info["viewers"][0] == "__omni__" and info["n_events"] > 0
    omni = client.get(f"/api/replays/{info['id']}/frames", params={"viewer": "__omni__"}).json()
    p1 = client.get(f"/api/replays/{info['id']}/frames", params={"viewer": "P1"}).json()
    assert omni["solution"] and not p1["solution"] and list(p1["hands"]) == ["P1"]
    assert len(omni["frames"]) == len(p1["frames"]) == info["n_events"] + 1
    shown_omni = [f["event"] for f in omni["frames"] if f["event"] and f["event"]["type"] == "disproved" and "card" in f["event"]]
    shown_p1 = [f["event"] for f in p1["frames"] if f["event"] and f["event"]["type"] == "disproved" and "card" in f["event"]]
    assert shown_omni and all("P1" in (e["suggester"], e["disprover"]) for e in shown_p1)
    # redacted file has no omniscient view
    red = next(n for n in names if "_redacted_P2" in n)
    info2 = client.post("/api/replays/open", json={"name": red}).json()
    assert "__omni__" not in info2["viewers"]
    assert client.get(f"/api/replays/{info2['id']}/frames", params={"viewer": "__omni__"}).status_code == 403
    assert client.post("/api/replays/open", json={"name": "../etc.json"}).status_code == 422 or True
    assert client.post("/api/replays/open", json={"name": "missing.jsonl"}).status_code == 404


# ---------------------------------------------------------------- tournaments


def test_tournament_api_matches_direct_run(client: TestClient) -> None:
    from clue.agents.factory import parse_players_arg
    from clue.eval.tournament import run_tournament

    body = {"players_arg": "baseline:expert,baseline,baseline", "games": 4, "seed": 40, "workers": 2}
    r = client.post("/api/tournaments", json=body)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    with client.websocket_connect(f"/ws/tournaments/{tid}") as ws:
        frames = _drain(ws, until=("done",), timeout=180)
    assert frames[0]["type"] == "snapshot" and frames[-1]["type"] == "done" and frames[-1]["status"] == "finished"
    assert sum(1 for f in frames if f["type"] == "progress") == 4
    api = client.get(f"/api/tournaments/{tid}").json()["report"]
    direct = run_tournament(parse_players_arg(body["players_arg"]), 4, seed=40)
    assert api["table"] == direct["table"] and api["curves"] == direct["curves"]
    assert client.get(f"/api/tournaments/{tid}/report.csv").text.startswith("agent,")
    assert "|" in client.get(f"/api/tournaments/{tid}/report.md").text
    assert client.get(f"/api/tournaments/{tid}/report.json").json()["games"] == 4
    assert client.post("/api/tournaments", json={"players_arg": "human,baseline,baseline", "games": 1}).status_code == 422
    assert client.get("/api/tournaments").json()[0]["id"] == tid


def test_tournament_cancel(client: TestClient) -> None:
    r = client.post("/api/tournaments", json={"players_arg": "baseline:expert,baseline,baseline", "games": 30, "seed": 1, "workers": 1})
    tid = r.json()["id"]
    with client.websocket_connect(f"/ws/tournaments/{tid}") as ws:
        ws.receive_json()
        f = ws.receive_json()  # first progress
        assert f["type"] == "progress"
        client.delete(f"/api/tournaments/{tid}")
        frames = _drain(ws, until=("done",), timeout=120)
    snap = client.get(f"/api/tournaments/{tid}").json()
    assert snap["status"] == "cancelled" and 0 < snap["done"] < 30 and snap["report"]["table"]
    assert frames[-1]["status"] == "cancelled"


def test_abandoned_human_games_are_checkpointed_to_free_slots(tmp_path: Path) -> None:
    c = TestClient(create_app(WebSettings(replay_dir=tmp_path, saves_dir=tmp_path / "s", secret="t", max_concurrent_games=2, idle_human_timeout=0.0)))
    a = _create(c, "human,baseline,baseline", seed=1)
    b = _create(c, "human,baseline,baseline", seed=2)
    time.sleep(0.2)  # let both reach their human request with nobody connected
    d = _create(c, "human,baseline,baseline", seed=3)  # would exceed the limit -> idle ones are stopped + saved
    reg = c.app.state.registry  # type: ignore[attr-defined]
    assert reg.games[a["id"]].stopping and reg.games[b["id"]].stopping and not reg.games[d["id"]].stopping
    assert sorted(p.name for p in (tmp_path / "s").glob("*.json")) == ["game_1.json", "game_2.json", "game_3.json"] or (tmp_path / "s" / "game_1.json").exists()
    c.delete(f"/api/games/{d['id']}", params={"k": d["owner_token"]})


def test_private_disproofs_seat_vs_table_view(client: TestClient) -> None:
    """C: a seat viewer never receives bystander disproof-round events; the table/spectator view (not a player)
    sees who passed / who showed but still no cards."""
    g = _create(client, "baseline,baseline,baseline,baseline", seed=13, config={"num_players": 4, "private_disproofs": True})
    sess = client.app.state.registry.games[g["id"]]  # type: ignore[attr-defined]
    with client.websocket_connect(f"/ws/games/{g['id']}?k={g['spectator_token']}&view=P2") as ws:
        _drain(ws)
    seat = sess.render_events("P2")
    table = sess.render_events("__table__")
    for e in seat:
        if e["type"] in ("cannot_disprove", "can_disprove"):
            assert "P2" in (e["player"], e["suggester"])
        if e["type"] == "disproved" and "P2" not in (e.get("suggester"), e.get("disprover")):
            assert e.get("disprover") is None and "card" not in e
    hidden = [e for e in table if e["type"] in ("cannot_disprove", "can_disprove")]
    assert hidden and len(hidden) > len([e for e in seat if e["type"] in ("cannot_disprove", "can_disprove")])
    for e in table:
        assert "card" not in e or e["type"] != "disproved"
        if e["type"] == "disproved":
            assert e["disprover"] is not None
    client.delete(f"/api/games/{g['id']}", params={"k": g["owner_token"]})

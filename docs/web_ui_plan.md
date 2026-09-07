# Web UI — Plan (Phase 7)

Status: **implemented (M0–M7)**, including remote multi-browser seats (per-seat HMAC tokens, waiting room with
presence, host force-start, reconnection via snapshot). User guide: `web.md`.
Deviations from the plan: Playwright cannot run in the build sandbox, so browser smoke tests are jsdom + real
WebSocket integration tests (`web/src/__tests__/live.integration.test.tsx`, skipped when no server is up); abandoned
human games are checkpointed and reclaimed after `idle_human_timeout` so the concurrent-game cap is never exhausted.

Decisions taken with the user (2026-09-06):

| Question | Decision |
|---|---|
| Frontend stack | **React + Vite + TypeScript** (separate `web/` package, built assets served by FastAPI) |
| Scope | **Everything**: play/spectate a game, replay viewer, tournament dashboard |
| Humans per game | **1 human seat by default**; **hot-seat (several humans, one browser) behind a flag**; **remote multi-browser seats = stretch milestone** |
| Deployment | **LAN / shared host, light protection**: bind `0.0.0.0`, per-game secret links, no accounts |

Hard constraints carried over from the spec: the rules engine and manager stay UI-agnostic (`clue/rules`, `clue/manager` import nothing from `clue/web`); privacy is enforced **server-side** by the existing `redacted_for` / `get_observation` machinery — the browser never receives another seat's cards; all existing acceptance tests keep passing; the harness must still run fully offline (`npm` is needed only to *build* the frontend, and a prebuilt bundle is committed/packaged so `pip install` users get the UI without node).

---

## 1. Goals & non-goals

**Goals**
1. Play a game against the AI in a browser with feature parity to the TUI: board, notebook (with editable notes), guided action panel, event log, coach mode (`h`, gated, logged), pause/speed, omniscient spectating, save / resume, ponder mode.
2. Step through any replay file (`.jsonl` / redacted `.json`) in the browser with per-viewer redaction — parity with `clue replay --tui`.
3. Launch tournaments from the browser and watch win-rate / ELO / candidate-count curves update live as games finish (reuses `run_tournament(..., on_game=, workers=)`).
4. Several browsers may **watch** the same game; one owns the human seat.
5. Hot-seat: `--hotseat` lets N human seats share one browser with a "pass the device" privacy screen between turns.

**Non-goals for this phase** (kept as explicit later milestones)
- Accounts, OAuth, TLS termination, Docker image, per-user LLM budgets (public deployment was not chosen).
- Mobile-first layout (it should not be broken on a tablet, but desktop is the target).
- Replacing the TUI. Both UIs share the same adapter layer; the TUI stays the CLI default.

## 2. Architecture

```
browser (React SPA)  ──HTTP JSON──▶  FastAPI  ──▶  GameSession  ──▶  run_game(gm, agents, on_events, stop, autosave)
                     ◀──WebSocket──  (clue/web)     (one thread          │
                                                     per game)           └─ WebHumanAgent  (same Request/queue pattern as TUIHumanAgent)
```

### 2.1 Reuse, don't rewrite
The TUI already isolates everything the web needs; the web layer is a second adapter over the same seams:

| Need | Existing seam | Web use |
|---|---|---|
| Human decisions | `Request` + blocking `queue.Queue` reply (`TUIHumanAgent._ask`) | `WebHumanAgent` posts the request to the session; HTTP `POST /act` puts the reply. `None` reply → `GameInterrupted` (already implemented for `q`). |
| Game loop | `run_game(gm, agents, on_events, ponder, autosave, stop)` | unchanged; runs in a session thread |
| Per-seat privacy | `gm.get_observation(pid)`, `Event.redacted_for(viewer)` | every WS frame is rendered per subscriber's viewer |
| Board geometry | `clue/tui/board_render.py` (`_room_cells`, grid, doors) | exported once as JSON (`GET /api/board`) and drawn as SVG |
| Coach hints | `action_coach` logic → extract to `clue/tools/coach.py` (`coach_hints(gm, pid) -> dict`) | shared by TUI and web; the "coach used" log note stays |
| Save/resume | `gm.save/load/restore_agents`, `--resume` | `POST /games/{id}/save`, `POST /games` with `{resume: path}` |
| Replays | `clue/tui/replay_viewer.py::ReplayState` (pure, no Textual) | move to `clue/replay/state.py`; server streams the pre-computed frames |
| Tournaments | `run_tournament(on_game=, workers=)` | session thread + WS progress frames |
| Agent construction | `make_agent(spec, ui=...)` factory | `ui="web"` returns `WebHumanAgent` for `kind="human"` |

Small refactors that fall out of this (each a tiny, tested PR before web code): `coach_hints()` extraction, `ReplayState` move, `board geometry → dict` function, `describe_event` already lives in `clue/agents/human.py` (fine).

### 2.2 Backend: `clue/web/`
```
clue/web/
  __init__.py
  server.py        FastAPI app factory `create_app(settings)`; mounts /api, /ws, and static SPA (catch-all → index.html)
  settings.py      pydantic-settings: host, port, secret salt, replay_dir, saves_dir, hotseat flag, max_concurrent_games, allowed_origins
  sessions.py      SessionRegistry (in-memory, thread-safe): create/get/list/close; GameSession, ReplaySession, TournamentSession
  game_session.py  owns gm+agents+thread; event fan-out; pending Request; pause/speed; save; per-viewer frame rendering
  human_agent.py   WebHumanAgent(PlayerAgent) — Request/queue pattern; `ask()` raises GameInterrupted on None
  schemas.py       pydantic models for every request/response/WS frame (explicit schemas per spec)
  auth.py          per-game secret links: game id = random 6-char code, `?k=<token>`; `owner` token vs `spectator` token
  routes/
    games.py       REST for lobby/game control
    replays.py     list/open replay files, frame endpoint
    tournaments.py start/stop/list; report download
    meta.py        /api/board, /api/catalog (strategies, bot kinds, providers, models), /api/health
  ws.py            WebSocket endpoint; subscription = (session, viewer, token); server pushes frames, never trusts client viewer beyond token rights
```
Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `websockets` (via uvicorn) → new optional extra `pip install -e ".[web]"`. Tests use `fastapi.testclient` + `starlette` WebSocket test client (no server process needed).

Threading model: `GameSession` runs `run_game` in a daemon thread exactly like `ClueApp._game_loop`. FastAPI handlers are sync-safe: they only touch the session through a lock and a `queue`/`asyncio.Queue` bridge (`loop.call_soon_threadsafe`) to push frames to WS subscribers. One process, many games; `max_concurrent_games` default 8. Human seats block only their own game's thread.

### 2.3 Frontend: `web/`
```
web/
  package.json      react, react-dom, react-router, zustand (state), vite, typescript, vitest, @testing-library/react
  src/
    api/            fetch wrappers + generated TS types (from /api/openapi.json via openapi-typescript at build)
    ws/             reconnecting WebSocket hook, frame reducer
    pages/          Lobby, Game, Replay, Tournaments, TournamentDetail
    components/
      Board.tsx     SVG board: rooms, doors, passages, tokens, reachable-square overlay, click-to-move
      Notebook.tsx  matrix (cards × players) w/ marks, editable notes cell, "hard deductions" shown only when coach on
      ActionPanel.tsx  guided flow (roll/passage/suggest/accuse/end turn; step pickers; card-to-show)
      EventLog.tsx  redacted log with per-viewer copy, auto-scroll, filter
      Omniscient.tsx  spectator table (solution + all hands + per-seat candidate counts)
      StatusBar.tsx viewer / turn / speed / pause / cost (LLM) / ponder stats
      HotseatGate.tsx "Pass to <seat>" curtain (only with hotseat flag)
      Curves.tsx    tournament candidate-count curves & win-rate CI (lightweight SVG/`recharts`)
    styles/         CSS modules; text-presentation glyphs (no colour emoji — known misalignment issue)
  vite.config.ts    dev proxy `/api`,`/ws` → `http://localhost:8000`; build output → `clue/web/static/`
```
Build output (`clue/web/static/`) is committed and included in `package_data`, so `pip install` + `clue web` works with no node. CI adds a `web` job: `npm ci && npm run typecheck && npm test && npm run build` and fails if the built bundle differs from the committed one (guards stale bundles).

## 3. API design

All ids are opaque strings; all bodies/responses have pydantic schemas in `schemas.py` (mirrored to TS).

### 3.1 REST
| Method & path | Purpose |
|---|---|
| `GET /api/health` | version, uptime, active sessions |
| `GET /api/catalog` | bot kinds, strategies (`strategies/*.md`), providers, known models, tool modes, defaults |
| `GET /api/board` | static geometry: grid, rooms → cells, doors, passages, start squares |
| `POST /api/games` | body: `{players: [PlayerSpec], seed?, config?, ponder?, delay?, autosave?} \| {resume: path}`. Returns `{id, owner_token, spectator_token, seats}` |
| `GET /api/games` / `GET /api/games/{id}` | list / snapshot (`state` redacted for the token's viewer, legal actions if it's your turn) |
| `POST /api/games/{id}/act` | body `{request_id, action}` or `{request_id, card}`; owner only; validated with `is_legal` before reply; 409 if no pending request / stale `request_id` |
| `POST /api/games/{id}/control` | `{pause}`, `{speed}`, `{viewer}` (spectator view cycling; only omniscient/any seat when no human seat, else own seat only) |
| `POST /api/games/{id}/coach` | returns `coach_hints` for the owner's seat; logs `coach_used` note (same as TUI) |
| `PUT /api/games/{id}/notes` | `{card, player, note}` → `gm.notebooks[pid].notes` (human seat only) |
| `POST /api/games/{id}/save` | writes checkpoint via `gm.save(path, agents)`; returns path |
| `DELETE /api/games/{id}` | stop (save first if unfinished), free session |
| `GET /api/saves` | list resumable checkpoints in `saves/` |
| `GET /api/replays` · `POST /api/replays/open` · `GET /api/replays/{id}/frames?viewer=` | list files; open; frames (whole list, precomputed, redacted per requested viewer) |
| `POST /api/tournaments` · `GET /api/tournaments/{id}` · `DELETE …` | start (`players, games, seed, workers, ponder, max_usd`), status + partial table/ELO/curves, cancel |
| `GET /api/tournaments/{id}/report.(csv\|json\|md)` | download (existing writers) |

### 3.2 WebSocket `/ws/games/{id}?k=<token>`
Server → client frames (`type` discriminated union):
- `snapshot` — full redacted observation for this viewer + `seats`, `phase`, `turn`, `finished`, `paused`, `speed`, `pending_request?` (only if it's this viewer's decision: `request_id`, `kind`, `legal[]`/`cards[]`).
- `events` — `[redacted event…]` + `log_lines[]` (already rendered via `describe_event`) — appended.
- `request` — a new human decision is pending for this viewer.
- `ponder` — per-seat ponder status (if enabled).
- `finished` — summary (winner, solution, stats, replay paths).
- `error` — human-readable (illegal action rejected, budget exceeded, …).

Client → server: only `{"type":"ping"}`; all mutations go through REST so they're validated, logged and testable with the normal test client.

Redaction rule: **the viewer is derived from the token, never from the message.** Owner token → their seat (or omniscient/any seat if the game has no human seat, matching the TUI's spectator rule). Spectator token → omniscient/any seat if no humans in game, otherwise **redacted "table view"** (what a bystander at the table would see: positions, public events, no hands). With hot-seat enabled, the owner token may switch viewer to any human seat only via the curtain flow (server tracks `active_human_seat`; the frame for a seat is only sent after the acknowledged handoff).

### 3.3 Security (LAN level)
- Game ids are random; tokens are `hmac(secret, id, role)` — links are unguessable, no accounts.
- `--host` default `0.0.0.0` when `clue web`, CORS restricted to same origin (+ Vite dev origin in dev mode).
- Paths for resume/replay open are restricted to `saves/` and `replays/` (no arbitrary file reads).
- LLM keys never leave the server; the catalog exposes model *ids* only. `max_usd` is enforced by the existing `CostTracker`; the UI shows spend live.
- Rate limit `POST /games` and `/tournaments` (simple token bucket per IP) so a LAN peer can't fork-bomb the host.

## 4. Milestones

Each milestone is independently shippable, lint/type/test clean, and updates docs. Estimates are rough working sessions.

| # | Milestone | Deliverable | Acceptance |
|---|---|---|---|
| **M0** | Seams refactor | `coach_hints()`, `ReplayState` move, `board_geometry()`; TUI uses them | all 106 tests pass unchanged; no behaviour change |
| **M1** | Backend core | `clue/web` with games REST+WS, `WebHumanAgent`, sessions, tokens, `clue web` command (`--host/--port/--hotseat/--open`) | pytest: full bot game streams to a WS spectator; a human seat driven purely through `/act` finishes a game with **0 illegal attempts**; a wrong-token viewer never receives another seat's hand (assert on every frame); stale `request_id` → 409; save+resume through the API reproduces replay hash |
| **M2** | Frontend: play & spectate | Lobby, Game page (Board SVG, Notebook, ActionPanel, EventLog, StatusBar), omniscient view, coach, pause/speed, save/quit | vitest component tests; Playwright smoke: create game, play one human turn, see events; manual parity checklist vs TUI (docs/playing.md table) |
| **M3** | Hot-seat flag | `--hotseat`, `HotseatGate` curtain, server-side active-seat gating | test: with two human seats, frames for seat B are never emitted before A's handoff is acknowledged |
| **M4** | Replay viewer | Replays page: pick file, viewer selector (redaction), step/auto-play, board+notebook+log at each frame | frames equal `ReplayState` outputs used by the TUI viewer (shared code, golden test) |
| **M5** | Tournament dashboard | Start form (players/games/seed/workers/ponder/max_usd), live progress, table with Wilson CIs & ELO, candidate curves, downloads | test: 4-game mock tournament via API → final table equals `run_tournament` direct call |
| **M6** | Packaging & polish | committed bundle in `clue/web/static`, `[web]` extra, CI web job with bundle-drift check, README/docs (`docs/web.md` + screenshot), keyboard shortcuts parity (`r p s a e h v space + -`), a11y pass (focus order, aria-live on log) | `pip install .[web] && clue web` works without node; CI green |
| **M7** *(stretch, later)* | Remote seats | seat tokens (`/api/games/{id}/seats/{pid}/claim`), room code join page, presence, reconnection resume | two test clients each own a seat and complete a game; privacy assertions per seat |

Suggested order for the first approval batch: **M0 → M1 → M2** (a playable browser game end-to-end), then review before M3–M6.

## 5. Testing strategy

- **Backend (pytest, no node needed):** `TestClient` + WS test client. Property: for every frame sent to viewer *v*, `assert frame ⊆ gm.get_observation(v)`-derived data (reuse `test_no_leak_in_redacted_replay` approach: the other seats' cards and the solution must not appear anywhere in the JSON text unless *v* is omniscient). Runner determinism: a game played through the API with a scripted human (first legal action) has the same replay hash as the same script through `TUIHumanAgent`.
- **Frontend (vitest + RTL):** reducers (frame → store), ActionPanel state machine (mirrors TUI `mode`/`_build` steps), Board reachable-square overlay from a fixture snapshot.
- **E2E (Playwright, optional CI job, `--headed` locally):** spectate a bot game to completion at high speed; play 3 human turns; open a replay; start a 2-game tournament.
- Existing suite stays untouched; web tests are skipped automatically if `fastapi` isn't installed (`pytest.importorskip`) so the offline core remains dependency-light.

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Thread/asyncio bridging bugs (frames lost or delivered after close) | single `SessionBus` with `loop.call_soon_threadsafe`; bounded queues; tests for close-while-pending |
| Privacy regression via a new serialisation path | one function `render_frame(session, viewer)` is the *only* place that builds outbound data; leak test runs on every frame in CI |
| Committed bundle goes stale | CI bundle-drift check; `make web` target |
| Bundle size / node in CI | Vite + React ≈ 150 kB gz; CI caches `~/.npm` |
| Long LLM turns block the human's browser feel | `request`/`ponder` frames + "thinking…" indicator; `delay` only applies to bot turns (as in TUI) |
| Two tabs owning the same seat | last `act` wins by `request_id`; UI shows "answered elsewhere" |
| Hot-seat leak by refresh | curtain state is server-side; a refresh re-shows the curtain, not the seat |

## 7. Open questions (non-blocking; defaults in bold)

1. Board rendering fidelity: **SVG drawn from `board_geometry()` in the "hybrid" grid** (same squares as the TUI) vs. a bitmap of the real board — SVG keeps click-to-move exact and diff-able.
2. Should the web lobby be able to edit `game.yaml`-level rules (dice, uneven deal toggle)? **Yes, expose `GameConfig` fields** — it's already a pydantic model.
3. Persist sessions across server restarts? **No** — autosave covers games (resume from `saves/`); tournaments write partial reports.
4. Charting lib: **hand-rolled SVG** for curves (≤ 3 chart types) to avoid a heavy dep; switch to `recharts` if it grows.

---

**Next step:** on approval, start M0 (seam refactors) and M1 (backend + tests), then M2. Each will be reported with the usual test/lint/type summary.

# Web UI

A browser front end with the same capabilities as the TUI, plus a replay viewer and a live tournament dashboard.
Design and milestones: `web_ui_plan.md`. Backend: `clue/web/` (FastAPI). Frontend: `web/` (React + Vite + TypeScript),
prebuilt into `clue/web/static/` so **no node is needed to run it**.

```bash
pip install -e ".[web]"
clue web                      # http://localhost:8000  (binds 0.0.0.0 -> reachable on your LAN)
clue web --hotseat --open     # allow several human seats in one browser; open the browser
clue web --port 9000 --saves-dir saves --replay-dir replays --max-usd 0.50
```
API docs (OpenAPI): `/api/docs`.

## Pages

| Page | What it does |
|---|---|
| **Play** (`/`) | Lobby: 3–6 seats (`human` / `baseline: heuristic·expert·random` / `llm: strategy·tool mode·model`), seed, dice, uneven-deal toggle, AI pace, ponder, provider. Lists resumable checkpoints (`saves/`) and games running on the server. |
| **Game** (`/game/<id>?k=<token>`) | SVG board (click a highlighted square/room to move), guided action panel, hand, notebook with private notes, un-redacted log for spectators, omniscient "all hands" table, coach mode, pause/speed, save, quit-and-save. |
| **Replays** (`/replays`) | Step through any replay file; choose the viewer (omniscient for unredacted files, or any seat) — redaction is applied server-side; shows the seat's private reasoning records. |
| **Tournaments** (`/tournaments`) | Start AI-only tournaments (games, seed, `workers` 0 = all cores, ponder, `max $`), watch progress live, win-rate with 95 % CI, ELO, candidate-count curves, download CSV/JSON/MD. |

### Keys in a game
`r` roll · `p` passage · `s` suggest · `a` accuse · `e` end turn · `Esc` back · `space` pause AI ·
`+`/`-` pace · `h` coach · `v` cycle spectator view · `ctrl+s` save · `q` quit & save.
Replay viewer: `→`/`n` next · `←`/`b` back · `space` autoplay · `g`/`G` start/end · `+`/`-` speed · `v` viewer.

## Links, roles, privacy

Every game gets two secret links: **owner** (`?k=<owner token>`) and **spectator**. Tokens are HMACs of the game id
and role with a per-process secret (`CLUE_WEB_SECRET` to make them stable across restarts); there are no accounts.

Redaction happens **on the server**, keyed by the token — never by anything the browser sends:

| Token | Game has a human seat | Bots only |
|---|---|---|
| owner | sees their own seat (hot-seat: the active seat) | omniscient by default; `?view=P2` to look through a seat |
| spectator | *table view*: positions and public events only, no hands | omniscient / any seat, like the TUI spectator |

The frames sent over the WebSocket are produced by one function (`GameSession.render_state/render_events/render_request`),
and `tests/test_web.py` asserts on every frame that a seat viewer never receives other hands, the solution
(before game over) or cards shown between other players.

## Hot-seat (`--hotseat`)

Several `human` seats share one browser. When the turn passes to another human, the server marks a **handoff
pending** and withholds that seat's private data (hand, notebook, request) until the player presses
"I am P2 — show my hand" (`POST /control {acknowledge_seat}`). A page refresh re-shows the curtain, not the hand.
Without the flag, games with more than one human seat are rejected.

## Save / resume

Games autosave to `saves/game_<seed>.json` after every action (the same format `clue play --save` uses, so a browser
game can be resumed in the TUI and vice-versa). `ctrl+s`/**Save** writes on demand; **Quit & save** stops the bots at
the next safe point and unblocks any pending human prompt. Resume from the lobby list. If a browser disappears while
the game waits on a human, the server checkpoints and stops the game after `idle_human_timeout` (10 min) — or sooner
when it needs the slot (`max_concurrent_games`, default 8).

## LLM seats & spend

LLM seats use the server's provider and keys from `.env`; keys never reach the browser. `--max-usd` caps spend for the
whole server (`CostTracker`); running spend shows in the status bar and on the tournament page. `mock` is offline.

## API summary

```
GET  /api/health | /api/board | /api/catalog | /api/saves | /api/replays | /api/games | /api/tournaments
POST /api/games            {players|players_arg, seed?, config?, ponder?, delay?, provider?, autosave?} | {resume}
GET  /api/games/{id}?k=&view=           snapshot for that viewer
POST /api/games/{id}/act?k=             {request_id, action|card, player?}    (422 illegal, 409 stale/no request)
POST /api/games/{id}/control?k=         {pause?, delay?, acknowledge_seat?}
POST /api/games/{id}/coach?k=           gated solver hints (logged as coach_mode_on)
PUT  /api/games/{id}/notes?k=           {note}
POST /api/games/{id}/save?k=            {name?}
DELETE /api/games/{id}?k=               stop (checkpoints first)
POST /api/replays/open {name} ; GET /api/replays/{id}/frames?viewer=
POST /api/tournaments {players_arg, games, seed, workers, ponder, max_usd} ; GET .../{id} ; DELETE .../{id} ; GET .../{id}/report.(csv|json|md)
WS   /ws/games/{id}?k=&view=   frames: snapshot | events | request | control | finished | stopped | error
WS   /ws/tournaments/{id}      frames: snapshot | progress | done
```

## Development

```bash
cd web && npm ci
npm run dev                          # Vite on :5173 with /api and /ws proxied to :8000
clue web --dev-origin http://localhost:5173
npm test && npm run typecheck        # vitest (component + reducer tests); live.integration.test.tsx runs when a server is up
npm run build                        # -> clue/web/static (commit it; CI fails on drift)
```
Layering: `clue/web` imports the manager, agents and tools; nothing below it imports `clue/web`. Web tests are
skipped automatically when `fastapi` is not installed, so the offline core stays dependency-light.

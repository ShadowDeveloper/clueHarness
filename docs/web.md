# Web UI

The shipped browser front end supports gameplay, replay viewing, tournaments, hot-seat play, and per-seat remote
invites. Backend: `clue/web/` (FastAPI). Frontend: `web/` (React + Vite + TypeScript),
prebuilt into `clue/web/static/` so **no node is needed to run it**.

```bash
pip install -e ".[web]"
clue web                      # http://localhost:8000  (binds 0.0.0.0 -> reachable on your LAN)
clue web --hotseat --open     # allow several human seats in one browser (pass the device); open the browser
clue web --no-remote          # disable remote seats (default: on - one invite link per human, several browsers)
clue web --port 9000 --saves-dir saves --replay-dir replays --max-usd 0.50
```
API docs (OpenAPI): `/api/docs`.

## Pages

| Page | What it does |
|---|---|
| **Play** (`/`) | Lobby: edition-aware seats (Classic/Modern: 3–6; Large: 3–12) (`human` / `baseline: heuristic·expert·random` / `llm: strategy·tool mode·model`), seed, rules, AI pace, ponder, provider. Lists resumable checkpoints (`saves/`) and games running on the server. |
| **Game** (`/game/<id>?k=<token>`) | Responsive browser layout with an **SVG mansion board** (rooms, doors, passages, tokens, reachable-square overlay, and click-to-move), **Notebook** (`✔ has  ✘ hasn't  ? unknown`), **Deductions**, Coach, event log, and guided action panel. |
| **Analyst** (`/analyze`) | Enter a *real-table* game (your cards + observed suggestions/facts) and get live posterior probabilities, hard deductions, opponent threat, and coach-style guidance. All math runs client-side (`web/src/analysis/`, a cross-validated TypeScript port of the Python solver); sessions autosave to localStorage and import/export the same JSON as `clue analyze` (see [analyst.md](analyst.md)). Also deployed standalone (no backend) to [GitHub Pages](https://shadowdeveloper.github.io/clueHarness/) by `.github/workflows/pages.yml`. `POST /api/analyze` returns the authoritative Python report. |
| **Replays** (`/replays`) | Step through any replay file; choose the viewer (omniscient for unredacted files, or any seat) — redaction is applied server-side; shows the seat's private reasoning records. |
| **Tournaments** (`/tournaments`) | Start AI-only tournaments (games, seed, `workers` 0 = all cores, ponder, `max $`), watch progress live, win-rate with 95 % CI, ELO, candidate-count curves, download CSV/JSON/MD. |

### Keys in a game
`r` roll · `p` passage · `s` suggest · `a` accuse · `e` end turn · `Esc` back · `space` pause AI ·
`+`/`-` pace · `h` coach · `v` cycle spectator view · `i` invite links (remote host) · `ctrl+s` save · `q` quit & save.
Replay viewer: `→`/`n` next · `←`/`b` back · `space` autoplay · `g`/`G` start/end · `+`/`-` speed · `v` viewer.

## Links, roles, privacy

Every game gets two secret links: **owner** (`?k=<owner token>`) and **spectator**. Tokens are HMACs of the game id
and role with a per-process secret (`CLUE_WEB_SECRET` to make them stable across restarts); there are no accounts.

Remote games add one **seat link** per human (`?k=<seat token>`, role `seat:P2`).
Redaction happens **on the server**, keyed by the token — never by anything the browser sends:

| Token | Game has a human seat | Bots only |
|---|---|---|
| owner (host) | sees their own seat (hot-seat: the active seat; remote: P1 if the host plays, else table view) | omniscient by default; `?view=P2` to look through a seat |
| seat:`Pn` | exactly that seat: its hand, notebook, requests; `?view=` is ignored; `/act` only for that seat | — |
| spectator | *table view*: positions and public events only, no hands | omniscient / any seat, like the TUI spectator |

The frames sent over the WebSocket are produced by one function (`GameSession.render_state/render_events/render_request`),
and `tests/test_web.py` asserts on every frame that a seat viewer never receives other hands, the solution
(before game over) or cards shown between other players.

## Hot-seat (`--hotseat`)

Several `human` seats share one browser. When the turn passes to another human, the server marks a **handoff
pending** and withholds that seat's private data (hand, notebook, request) until the player presses
"I am P2 — show my hand" (`POST /control {acknowledge_seat}`). A page refresh re-shows the curtain, not the hand.
Without the flag, games with more than one human seat are rejected.

## Remote seats (several browsers)

Pick *remote: one invite link per human* in the lobby (it is the default whenever there are 2+ humans and the server was
not started with `--hotseat`; a single human can also tick *play from another device*). The host page opens a
**waiting room** with one invite link per human seat (`GET /api/games/{id}/invites`, owner only) and live presence
dots; each player opens their link in their own browser. The game thread does not start until every seat has connected
once (the host can *Start anyway*; absent seats are simply waited on when their turn comes). Presence is pushed as
`presence` frames, shown next to the log; a seat that reloads gets a full snapshot and continues. A waiting room that
nobody joins is checkpointed and reclaimed like any abandoned human game.

Security model is unchanged: a seat token is an HMAC of `game:seat:Pn`; `resolve_viewer()` maps it straight to that
seat, `Access.human_seat()` refuses to act for any other seat, and the per-frame privacy test runs both seats of a
remote game to completion (`test_remote_seats_two_browsers_play_to_completion_with_per_seat_privacy`).
`CLUE_WEB_CREATE_RATE_PER_MINUTE` sets the per-client-IP limit for creating games/tournaments (default 20);
`CLUE_WEB_IDLE_HUMAN_TIMEOUT` sets how long a disconnected human game may wait before checkpointing (default
600 seconds). Other server settings are in `clue/web/settings.py`.

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
POST /api/games            {players|players_arg, seed?, config?, ponder?, delay?, provider?, autosave?, remote?} | {resume}
                           -> {id, owner_token, spectator_token, seat_tokens{Pn: token} (remote), humans, ...}
GET  /api/games/{id}?k=&view=           snapshot for that viewer
GET  /api/games/{id}/invites?k=         owner only: per-seat invite tokens + presence (remote games)
POST /api/games/{id}/act?k=             {request_id, action|card, player?}    (422 illegal, 409 stale/no request)
POST /api/games/{id}/control?k=         {pause?, delay?, acknowledge_seat?, start?}
POST /api/games/{id}/coach?k=           gated solver hints (logged as coach_mode_on)
PUT  /api/games/{id}/notes?k=           {note}
POST /api/games/{id}/save?k=            {name?}
DELETE /api/games/{id}?k=               stop (checkpoints first)
POST /api/replays/open {name} ; GET /api/replays/{id}/frames?viewer=
POST /api/tournaments {players_arg, games, seed, workers, ponder, max_usd} ; GET .../{id} ; DELETE .../{id} ; GET .../{id}/report.(csv|json|md)
WS   /ws/games/{id}?k=&view=   frames: snapshot | events | request | control | presence | finished | stopped | error
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


## Editions

The lobby has an **edition** selector: `classic` (6·6·9, 3–6 players), `modern` (Dr. Orchid) and `large` — *Hill House* (12 suspects, 12 weapons, 12 rooms, 3–12 players, 36×36 board with Attic, Cellar, Garage, Gazebo, Courtyard and Carriage House). `GET /api/board?edition=large` returns the matching geometry; `GET /api/catalog` lists editions with their card sets and player caps. Tournaments accept `config.edition` too.

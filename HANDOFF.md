# HANDOFF — Clue AI harness

_Last updated 2026-10-04. Repo head: `d4ae727`. Working tree clean except stray `replays/game_2_redacted_P*.json` (safe to delete)._

## 1. What this project is

A modular AI harness for Classic US Clue (3–6 players; 3–12 in the Large edition), built to the spec in
`AGENT_PROMPT.md` with rules locked in `RULES_SPEC.md`. Four separated layers: **rules** (`clue/rules`, pure,
never imports LLM code) → **manager** (`clue/manager`: notebooks, redaction, audit log, save/resume) →
**agents** (`clue/agents`: human CLI/TUI/web, baselines random/heuristic/expert, LLM with JSON retry + fallback)
→ **strategies** (`strategies/*.md`, prompt text only). Symbolic math tools in `clue/tools` (exact solver for ≤6
players, sampled solver beyond), eval/tournaments in `clue/eval`, Textual TUI in `clue/tui`, FastAPI + React web
UI in `clue/web` + `web/`.

**Everything in the spec is complete**, plus: ponder mode, exact solver/expert bot, save/resume, parallel
tournaments, full web UI (game, replay, tournament dashboard, hot-seat, remote invite links), Large edition,
and the opt-in variance-reduction variants A–F. There is no unfinished work in flight.

## 2. Standing user decisions (do not reverse without asking)

- Rules edition: Hasbro 2002, **2d6 default** (1d6 via config); uneven-deal handling is a config toggle; board is the "hybrid" model.
- LLM providers: OpenRouter + local OpenAI-compatible. Key lives in `.env` (gitignored) — never in code. Keep live runs small; `eval` is offline by default, `--live` opt-in.
- Solver hard deductions are **gated** behind coach mode for humans, never auto-shown. Expert bot is deterministic; strength maximised.
- Web UI: React + Vite + TS; LAN deployment with secret links, no accounts. Rules/manager stay UI-agnostic; privacy enforced server-side; the prebuilt bundle in `clue/web/static` is committed (pip users need no node). **Rebuild it (`cd web && npm run build`) and commit whenever `web/src` changes** — CI has a drift check.
- Variants A–F are **opt-in config toggles; classic defaults unchanged** (also not defaults for the Large edition).
- Under private disproofs, **web spectators/table view see the full disproof round**; only seated players are kept in the dark (user asked for this explicitly).
- Rejected and not to be revisited: character-grid web board (replaced by the SVG mansion), emoji weapon icons.
- Ask the user clarifying questions before planning/coding a new feature area.

## 3. How to run / verify

```bash
pip install -r requirements.lock.txt          # ruff/mypy/textual sometimes vanish from the sandbox — reinstall
cd web && npm ci && cd ..                     # node_modules is not persisted either
ruff check clue tests && ruff format --check clue tests && mypy clue
python -m pytest -q -p no:warnings            # 141 tests, ~4–5 min (expert games dominate)
cd web && npx tsc --noEmit -p . && npx vitest run && npm run build
python -m clue web                            # server entry (NOT clue.cli); bind 0.0.0.0, :8000
```
CLI: `clue play|replay|tournament|eval|live-eval|web`. Useful flags: `--edition classic|modern|large`,
`--variants private,skip=2,shuffle,teams[=K]`, `tournament --duplicate -w 0`, `play --ui tui|cli --spectate`.
Git commits need `-c user.name=... -c user.email=...` (no global identity in the sandbox).

## 4. Where things are

| Area | Files |
|---|---|
| Rules | `clue/rules/{state,engine,board,cards}.py` — `GameConfig`, `Event` (`private_to`, `hidden`, `visible_to`), `new_game`, `legal_actions`, `apply_action` |
| Manager | `clue/manager/game_manager.py` (`create/load/save`, `_fresh_notebook`, `public_history`, `export_replay`, `summary`), `notebook.py`, `runner.py`, `ponder.py` |
| Agents | `clue/agents/{factory,baselines,expert,llm_agent,llm_client,human}.py`, prompts `base_prompt.md`, `ponder_prompt.md` |
| Tools | `clue/tools/{solver,deduction,opponent}.py` |
| Eval | `clue/eval/{tournament,stats,report,live_eval}.py` — `run_tournament(..., rotate_seats, workers, duplicate)`, `duplicate_stats` |
| Config/CLI | `clue/config.py` (YAML), `clue/__main__.py` (typer; `parse_variants`) |
| TUI | `clue/tui/{app,replay_viewer,...}.py` |
| Web | `clue/web/{app,game_session,tournament_session,replay_session,human_agent,schemas}.py`, `clue/web/routes/*`, SPA in `web/src` (pages Lobby/Game/Replay/Tournaments, components Board/Notebook/EventLog) |
| Tests | `tests/test_{rules,manager,solver,expert,glue,llm_client,opponent,ponder,stats,tui,web,large_edition,variants}.py` |
| Docs | `README.md`, `RULES_SPEC.md`, `docs/*.md` (playing, web, configuration, architecture, observation_schema, replay_format, tools, strategies, extending, pondering, evaluation, **variants**, web_ui_plan) |

## 5. Gotchas learned the hard way

- `Board` dataclass must stay `eq=False` (identity hash; `_bfs` is `@cache`d on it). Board validator requires starts on corridor cells; `ROOM_RECTS` must not overlap starts/doors.
- Never seed RNG with `hash()` of strings — use `repr(seed_src)`.
- Exact DP solver is unusable beyond 6 players / 21 cards → sampled solver with node budget; running `_propagate` before the exact DP doubles classic expert time — keep it sampled-path only. Expert only gambles on sampled posteriors at p ≥ 0.9.
- Pydantic + mypy: use `Field(default=..., ge=...)`, not positional defaults, or mypy flags missing kwargs.
- FastAPI 0.141: `FileResponse | JSONResponse` routes need `response_model=None`. Mock-LLM games over `TestClient` take ~75 s — web tests use baseline players and must `DELETE` their games (registry cap `max_concurrent_games=8`). `turn_number` starts at 0; `game_over` includes `solution` publicly by design.
- TUI pilot tests need `await pilot.pause()`. Playwright is unavailable: web integration tests use jsdom + `ws` (4 skip without a live server — expected). SVG visual checks: render via `cairosvg` after stripping the `svg.board` prefix, `.board{}` size rule and `filter="url(#shadow)"`.
- `make_agent(spec, seed:int)`; `run_game(gm, agents, on_events=, stop=)`; `GameManager.get_observation(pid)` (not `observation`).
- `git stash` also stashes new test files; `git rm --cached` + `git add -A` in one shell re-adds ignored dirs.
- `openrouter/free` is unusable for live eval; keep live spend tiny.

## 6. Reasonable next steps (none requested yet — ask first)

- Measure the variants: run `tournament --duplicate` across A/C/D on expert vs heuristic and add a section to `docs/evaluation.md`.
- Web UI could show `house_rules` in the game header and render `penalised`/`turn_skipped` with distinct colours in `EventLog.tsx` (currently plain text).
- LLM strategy prompts don't yet exploit team mode (e.g. coordinating suggestions); only the `house_rules` note exists.
- `docs/web_ui_plan.md` is the original plan and now historical; could be trimmed.

# Clue / Cluedo AI Harness

A modular, fully-tested harness for playing **Classic US Clue (3–6 players)** with any mix of humans, LLM
agents (with pluggable strategy prompts) and scripted baseline bots — interactively or in batch tournaments.

```
clue/
  rules/      A) pure rules engine  (cards, board, state, engine)  — no LLM, no I/O
  manager/    B) game state manager (notebooks, privacy, replay, runner)
  agents/     C) PlayerAgent interface, baselines, human CLI, LLM agent + base_prompt.md, llm_client.py
  tui/        Textual full-screen interface for humans / spectating (board, notebook, log, action menu)
  web/        FastAPI backend (REST + WebSocket) + prebuilt React SPA in web/static: play, replays, tournaments
  replay/     UI-independent replay state reconstruction (shared by the TUI and web viewers)
  tools/      exact deduction solver, opponent model, symbolic tools shared by LLM agents and bots
  eval/       tournament runner (multiprocess), Wilson CIs / paired tests / fingerprints, offline + live eval
strategies/   D) strategy prompt fragments (*.md) — appended to the base prompt, never change legality
tests/        119 pytest tests (+12 vitest): rules, manager, TUI (headless), web API/WS privacy, ponder, solver, expert bot, LLM client, stats, glue
web/          React + Vite + TypeScript source of the web UI (npm run build -> clue/web/static; node not needed to run)
docs/         full documentation set (see docs/README.md)
RULES_SPEC.md rules edition + every edge-case decision
game.yaml     example config     demo_game.md  example transcript     eval/report.md  example eval
```

## Documentation
| | |
|---|---|
| [docs/playing.md](docs/playing.md) | TUI guide (panels, notebook symbols, hotkeys), plain CLI, spectating, save/resume |
| [docs/web.md](docs/web.md) | web UI: `clue web`, pages, secret links & server-side redaction, hot-seat, API, development |
| [docs/configuration.md](docs/configuration.md) | `game.yaml`, `--players` shorthand, `.env` providers, every CLI flag |
| [docs/architecture.md](docs/architecture.md) | the four layers, data flow, privacy & determinism model |
| [docs/observation_schema.md](docs/observation_schema.md) | every field an agent sees, with a real example |
| [docs/replay_format.md](docs/replay_format.md) | JSONL records, redaction rules, hash, checkpoints |
| [docs/tools.md](docs/tools.md) | symbolic deduction tools and their algorithms |
| [docs/strategies.md](docs/strategies.md) | writing and measuring strategy prompts |
| [docs/extending.md](docs/extending.md) | new provider / agent / rule variant / metric / UI |
| [docs/pondering.md](docs/pondering.md) | parallel thinking between turns (UCI-style ponder): lifecycle, interrupts, isolation |
| [docs/evaluation.md](docs/evaluation.md) | metrics, ELO, ablation semantics, acceptance evidence |
| [RULES_SPEC.md](RULES_SPEC.md) | rules edition and edge cases |

## 5-minute quickstart

```bash
pip install -e ".[dev]"          # installs the `clue` console command (python -m clue also works); requirements.lock.txt has exact pins
cp .env.example .env             # optional: add OPENROUTER_API_KEY etc. Defaults to the offline mock LLM.

# fully offline demo: 2 mock-LLM seats with strategies + 2 baselines
python -m clue play --players llm:bayesian,llm:aggressive,baseline,baseline:random --seed 7

# you vs 3 AIs — full-screen TUI (board, notebook grid, event log, action menu; mouse + keyboard)
python -m clue play --config game.yaml
python -m clue play --players human,llm:bayesian,llm:aggressive,baseline
python -m clue play --players llm:bayesian,baseline,baseline --spectate    # watch AIs omnisciently (space = pause, +/- speed, v = seat view)
python -m clue play --players human,baseline,baseline --ui cli             # plain-text fallback
python -m clue play --players llm:bayesian,llm:info,baseline,baseline --spectate --ponder   # AIs think between turns

# strongest offline opponent: baseline:expert (exact solver + expected-information-gain suggestions)
clue play --players human,baseline:expert,baseline,baseline        # press h in the TUI for coach mode (opt-in solver hints)
clue play --resume saves/game_0.json                                # continue a saved game (TUI autosaves; ctrl+s / q save too)
pip install -e ".[web]" && clue web --open                          # browser UI: play/spectate, replay viewer, tournament dashboard

# 100-game tournament with ELO, Wilson CIs, paired tests, candidate curves; --workers N plays N games at once (0 = all cores)
clue tournament --games 100 --players llm:bayesian,baseline:expert,baseline,baseline --seed 123 --report elo.csv --workers 4

# eval: random vs heuristic vs LLM+tools vs LLM no-tools (+strategy bracket) -> eval/report.md, eval/charts.png
python -m clue eval --games 50           # offline (MockLLM)
python -m clue eval --games 50 --live    # real provider from .env

# live LLM eval with a hard budget: tool-mode ablation + ponder brackets on paired seeds (see docs/evaluation.md)
clue live-eval --model nvidia/nemotron-3-super-120b-a12b:free --games 5 --max-usd 0.10

clue replay replays/game_7.jsonl           # pretty-print a replay
clue replay replays/game_7.jsonl --tui     # step through it on the board (n/b, space, v = viewer redaction)
pytest -q && ruff check clue tests && mypy clue      # 119 tests (~7 min), 93 % coverage, lint + strict types; CI: .github/workflows/ci.yml
```

### The TUI
```
 ⭘                                      Clue — P1: human  P2: baseline:heuristic  P3: baseline:heuristic  P4: baseline:heuristic                                          
╭─ Board ──────────────────────────────────────────────╮╭─ Notebook  ✔ has  ✘ hasn't  ? unknown ─────────────╮╭─ What happened ──────────────────────────────────────────╮
│     0 1 2 3 4 5 6 7 8 9 1011121314151617181920212223 ││ Card           P1  P2  P3  P4                      ││  P3 showed a card to P2                                  │
│  0                    ·         ·                    ││ Miss Scarlet   ?   ?   ✘   ?                       ││--- Turn 18: P3 ---                                       │
│  1              · · · ·         · · · ·              ││ Col. Mustard   ✔   ·   ·   ·   yours               ││P3 suggests: Col. Mustard with the Wrench in the          │
│  2              · ·                 · ·              ││ Mrs. White     ✘   ?   ?   ?                       ││Conservatory                                              │
│  3    KITCHEN   · ·                 · ·   CONSERV.   ││ Mr. Green      ✔   ·   ·   ·   yours               ││  P4 cannot disprove                                      │
│  4    ♣         · ·     BALLROOM    · ·              ││ Mrs. Peacock   ?   ?   ✘   ?                       ││  P1 can disprove...                                      │
│  5              · ▢   ♛ ✚ ✎         ▢ · l r       ⇄  ││ Prof. Plum     ?   ?   ?   ✘                       ││  P1 showed the Col. Mustard to P3                        │
│  6  d         ⇄ · ·                 · ★ ▢ · · · · ·  ││ Candlestick    ?   ?   ?   ?                       ││--- Turn 19: P4 ---                                       │
│  7    · · · ▢ · · · r w             · · · · · · ·    ││ Dagger         ?   ?   ?   ?                       ││P4 rolled [3, 5] = 8                                      │
│  8    · · · · · · · · ▢ · · · · ▢ · · ·              ││ Lead Pipe      ✔   ·   ·   ·   yours               ││P4 moved Conservatory -> Ballroom                         │
│  9                  · · · · · · · · · ▢              ││ Revolver       ✔   ·   ·   ·   yours               ││P4 suggests: Mrs. White with the Wrench in the Ballroom   │
│ 10                  · ░░░░░░░░░░░░· · ·   BILLIARD   ││ Rope           ✘   ?   ?   ✘                       ││  P1 can disprove...                                      │
│ 11                  · ░░░░░░░░░░░░· · ·              ││ Wrench         ✔   ·   ·   ·   yours               ││  P1 showed the Wrench to P4                              │
│ 12      DINING      ▢ ░░░░░░░░░░░░· · ·              ││ Hall           ?   ?   ✘   ?                       ││━━━ YOUR TURN ━━━                                         │
│ 13    ❋             · ░░░░░░░░░░░░· · · · · ▢ · ▢    ││ Lounge         ?   ?   ✘   ?                       ││P1 rolled [2, 6] = 8                                      │
│ 14                  · ░░░░░░░░░░░░· ·                ││ Dining Room    ?   ?   ?   ?                       ││P1 moved Ballroom -> Billiard Room                        │
│ 15  c               · ░░░░░░░░░░░░· ·                ││ Kitchen        ?   ?   ?   ?                       ││--- Turn 21: P2 ---                                       │
│ 16    · · · · · ▢ · · ░░░░░░░░░░░░· ▢   LIBRARY      ││ Ballroom       ?   ?   ?   ✘                       ││P2 rolled [1, 1] = 2                                      │
│ 17  · · · · · · · · · · · ▢ ▢ · · · ·                ││ Conservatory   ✘   ?   ?   ✘                       ││P2 moved Conservatory -> 6,17                             │
│ 18    · · · · · ▢ · ·             · ·                ││ Billiard Room  ?   ?   ?   ?                       ││--- Turn 22: P3 ---                                       │
│ 19                · ·             · · · · · · · · ·  ││ Library        ?   ?   ?   ?                       ││P3 suggests: Miss Scarlet with the Wrench in the          │
│ 20                · ▢             · · ▢ · · · · ·    ││ Study          ?   ?   ?   ?                       ││Ballroom                                                  │
│ 21      LOUNGE    · ·     HALL    · ·                ││                                                    ││  P4 can disprove...                                    ▃▃│
│ 22                · ·             · ·     STUDY      ││                                                    ││  P4 showed a card to P3                                  │
│ 23                · ·             · ·                ││                                                    ││--- Turn 23: P4 ---                                       │
│ 24              ⇄ ·                               ⇄  ││                                                    ││P4 rolled [6, 2] = 8                                      │
│                                                      ││                                                    ││P4 moved Ballroom -> Kitchen                              │
│  ♛   Miss Scarlet  ← you                             ││                                                    ││P4 suggests: Mr. Green with the Dagger in the Kitchen     │
│  ★   Col. Mustard                                    ││                                                    ││  P1 can disprove...                                      │
│  ✚   Mrs. White                                      ││                                                    ││  P1 showed the Mr. Green to P4                           │
│  ♣   Mr. Green                                       ││                                                    ││━━━ YOUR TURN ━━━                                         │
│  ❋   Mrs. Peacock                                    ││                                                    │╰──────────────────────────────────────────────────────────╯
│  ✎   Prof. Plum                                      ││                                                    │┏━ Your move ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│  ▢ door   ⇄ passage   ◆ reachable   ░ cellar         ││                                                    │┃ It's your turn.                                          ┃
│                                                      │╰────────────────────────────────────────────────────╯┃ • Roll the dice and move                                 ┃
│                                                      │╭─ Deductions ───────────────────────────────────────╮┃ • Suggest here in the Ballroom (you were brought here —  ┃
│                                                      ││ • P4 holds at least one of Mrs. Peacock, Wrench,   │┃ no need to move)                                         ┃
│                                                      ││ Lounge                                             │┃ Accuse only when sure — a wrong accusation eliminates    ┃
│                                                      ││ • P4 holds at least one of Mrs. Peacock, Dagger,   │┃ you.                                                     ┃
│                                                      ││ Dining Room                                        │┃                                                          ┃
│                                                      ││ • P3 holds at least one of Mrs. White, Wrench,     │┃ ▔▔▔▔▔▔▔▔▔▔ ▔▔▔▔▔▔▔▔▔▔▔▔▔ ▔▔▔▔▔▔▔▔▔▔▔▔                    ┃
│                                                      ││ Conservatory                                       │┃  Roll (r)   Suggest (s)   Accuse (a)                     ┃
│                                                      ││ • P4 holds at least one of Miss Scarlet, Wrench,   │┃ ▁▁▁▁▁▁▁▁▁▁ ▁▁▁▁▁▁▁▁▁▁▁▁▁ ▁▁▁▁▁▁▁▁▁▁▁▁                    ┃
╰──────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────╯┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
 You are ♛ Miss Scarlet (P1) in the Ballroom   ·   your cards: Col. Mustard, Lead Pipe, Mr. Green, Revolver, Wrench   ·   turn 24                                         
 r Roll  p Passage  s Suggest  a Accuse  e End turn  esc Back  space Pause  + Faster  - Slower  q Quit                                                        ▏^p palette
```
Guided action panel (only the buttons that apply right now, hotkey in every label, step-by-step pickers
with Back), graphical board with reachable squares highlighted after a roll, per-player notebook grid.
Built on Textual; the human seat is an ordinary `PlayerAgent` fed from the UI thread through a queue, so
game logic is identical for humans, bots and LLMs. See [docs/playing.md](docs/playing.md).

### Player shorthand for `--players`
`human` · `baseline[:heuristic|random|expert]` · `llm[:<strategy>[:<model>]][:notools|:native][:compact]`
Strategy aliases: `conservative, aggressive, bayesian, info_value_hunter, deceptive, room_rusher`, or a path to
your own `.md`. `--strategy path.md` sets a default strategy for LLM seats without one; `--no-tools` disables
the symbolic tool layer for all LLM seats (ablation).

### YAML config (`game.yaml`)
```yaml
edition: classic-clue-2002   # classic-clue-1996 (1 die) | classic-clue-2002 (2 dice) | modern (Dr. Orchid)
seed: 42
deal_remainder: uneven       # uneven (official) | faceup (house rule)
players:
  - {id: P1, kind: human, name: You}
  - {id: P2, kind: llm, model: openai/gpt-4o-mini, strategy: strategies/bayesian_probabilist.md, temperature: 0.2}
  - {id: P3, kind: llm, model: mock, strategy: strategies/deceptive_misdirector.md, tools: false}
  - {id: P4, kind: baseline, bot: heuristic}
```

## Rules edition
Hasbro *CLUE Classic Detective Game* instructions (https://www.hasbro.com/common/instruct/clueins.pdf, the
two-dice US edition). All decisions — uneven deal, accuse-from-anywhere, no re-entering a room in the same
turn, summoned players may suggest without moving, eliminated players keep disproving, hybrid board model —
are itemised in **[RULES_SPEC.md](RULES_SPEC.md)**. Config flags: `dice: 1|2`, `deal_remainder`,
`edition: classic|modern`, `max_turns`.

## Architecture: 4 separated mechanisms
| Layer | Package | Guarantees |
|---|---|---|
| A Rules Engine | `clue/rules` | Pure functions `new_game / legal_actions / apply_action / check_winner`; deterministic under a passed `random.Random`; `IllegalAction` on anything not in `legal_actions`; imports nothing outside `clue.rules`. |
| B Game State Manager | `clue/manager` | `GameManager.create / step / get_observation / export_replay / save / load / replay_hash`; per-player `Notebook` of *derived public facts*; `Event.private_to` redaction; JSONL replay incl. tool calls + agent notes; `runner.run_game` validates every agent action, retries once, then falls back (logged). Contains no strategy text and no LLM code. |
| C Agent Interface | `clue/agents` | `PlayerAgent.choose_action / choose_card_to_show`; `BaselineRandomBot`, `BaselineHeuristicBot`, `HumanCLIAgent`, `LLMPlayerAgent` (+ `base_prompt.md`, `llm_client.py` with OpenRouter / OpenAI / local-OpenAI-compatible / Anthropic / Mock). |
| D Strategy Layer | `strategies/*.md` | Text appended to the base system prompt. Cannot change `legal_actions`; the final action is always validated by the manager. |

Observation schema (`GameManager.get_observation`): `you`, `board` (tokens, `your_legal_moves`), `turn`,
`public_history` (redacted per viewer), `notebook`, `legal_actions`, `can_accuse`, `cards`, `config`. LLM
agents additionally receive `analysis` (pre-computed tool output) when tools are enabled.

## Stronger AI: exact solver, expert bot, opponent model

* `clue/tools/solver.py` — **exact** inference: counts every complete hand assignment consistent with the
  notebook (memoised DP; verified against brute force), giving exact envelope posteriors, per-card holder
  probabilities and forced facts. Hard deductions are **gated** for humans (coach mode only, never written to
  the notebook); bots and LLMs use them freely.
* `baseline:expert` — deterministic bot on top of the solver: accuses only when certain (or when the
  decision-theoretic gamble rule fires), picks suggestions by **expected information gain** (exact re-solve
  per disproof outcome), BFS room targeting through the real board, min-leak card showing. Wins ~40 % of
  seat-shuffled 4-player games against three heuristic bots (fair share 25 %) and 4/5 vs a live LLM.
* `clue/tools/opponent.py` — `opponent_threat()`: shadow notebooks + exact solver estimate how close each
  rival is to solving (correlation 0.97 with their true candidate count). Used by the expert bot and
  injected into LLM prompts as `analysis.opponent_threat`.

## Symbolic tools (`clue/tools/deduction.py`)
`get_unseen_cards`, `get_possible_solutions` (constraint-consistent combos), `solution_probabilities`
(rejection-sampled posterior over hand assignments), `suggestion_ev` (novelty / potential disprovers),
`can_accuse_confidently(threshold)`, `update_notebook(note)`, plus `best_suggestion`. LLM agents get the bundle
pre-computed in `analysis` together with a `recommended_action` from the heuristic policy, and every call is
logged as a `tool_call` record in the replay (private to that player). `--no-tools` removes all of it.

## Parallel thinking (`--ponder`)
Like a chess engine's ponder flag: while others act, idle AI seats run an interruptible background session
(`PlayerAgent.ponder(observation, ctx)`) on a snapshot of their knowledge — calling deduction tools, writing
notebook notes, preparing a plan. `PonderManager` stops them cooperatively when informative events occur
(restart on fresh data) or when their own turn begins (bounded grace, then the real decision), and never
lets a straggler block the game. Everything is logged privately as `ponder` records. Details in
[docs/pondering.md](docs/pondering.md).

## LLM tool modes & live hardening

`--tool-mode precomputed|native|none` (or `llm:<strategy>:native`), `--prompt-profile full|compact`,
`--max-usd` hard budget. The client has exponential backoff, timeouts, JSON mode with fallback, native
function calling with auto-degradation, an on-disk response cache (`CLUE_LLM_CACHE`) and per-model cost
accounting. Live eval (free OpenRouter model, 5 paired seeds/variant): with the tool layer the LLM was legal
and patient (0 premature accusations); without it, 60 % of games ended in a premature accusation and only
31 % of replies were valid JSON on the first try. Details: `docs/evaluation.md`, `eval/live_report_nemotron_free.md`.

## LLM robustness
Response must be JSON `{"reasoning", "action"|"card", "note"?}`; parsed leniently (fences/prose tolerated),
validated against `legal_actions` / accusation schema, one retry with the error message, then heuristic
fallback — all logged as `agent_note` records (`llm_response`, `llm_error`, `fallback_to_heuristic`).
Per-agent `stats` (`calls, valid_first_try, retries, fallbacks`) are printed after each game.

## Evaluation (offline, 50 games/bracket, seed 0 — see `eval/report.md`, `eval/charts.png`)
| agent | win_rate | false_accusation_rate |
|---|---|---|
| baseline:expert (new, exact solver + expected-info-gain) | 0.36 vs 3× heuristic (fair share 0.25) | 0.00 |
| baseline:heuristic | 0.56 | 0.00 |
| llm(mock)+tools (bayesian) | 0.30 | 0.00 |
| llm(mock) **no-tools** | 0.04 | 0.86 |
| baseline:random | 0.00 | 0.60 |

**Tools ablation:** LLM+tools beats LLM no-tools on both win-rate (0.30 vs 0.04) and false-accusation rate
(0.00 vs 0.86). Offline, the mock LLM follows the tool recommendation when tools are on and plays an
unguided legal action otherwise, so this measures the value of the symbolic layer. The heuristic still wins
more than mock-LLM+tools because the mock returns 2% garbage replies (exercising the retry/fallback path) and
uses a slightly different disproof policy; with a real model the gap depends on the model.

**Strategy swapping:** the strategy text only changes behaviour when a real model reads it; offline bracket B
is therefore noise (documented in the report). Run `python -m clue eval --live` with a key in `.env` to
measure it; the tournament table reports win-rate, `avg_turns_to_win` (accusation timing) and
`false_accusation_rate` per strategy label.

## Acceptance checklist
- [x] 4-player Human + 3 AI game to completion, zero illegal moves — `demo_game.md` (`illegal attempts = 0`)
- [x] Privacy — `tests/test_manager.py::test_no_leak_in_redacted_replay`, `replays/game_42_redacted_P3.json`
- [x] Determinism — `test_same_seed_same_replay_hash`, `test_save_load_roundtrip`
- [x] Valid-JSON rate: mock 100 %; live (nemotron free) 95.7 % first try with tools, 30.8 % without; invalid → 1 retry → heuristic fallback (`test_llm_agent_retry_then_fallback`)
- [x] Strategy swapping measurable via tournament labels (live) — see above
- [x] Tools ablation — 50-game offline eval above + live paired ablation (`eval/live_report_nemotron_free.md`)
- [x] Web UI (optional `[web]` extra): human seat over HTTP finishes a game with 0 illegal moves, per-frame privacy, API save/resume reproduces the replay hash, hot-seat gating, tournament API == direct run (`tests/test_web.py`, 13 tests) + 12 vitest tests
- [x] `pytest` (119 passed), `ruff check` + `ruff format --check` clean, `mypy --strict` clean; total coverage 93 % (CI gate 90 %)
- [x] Exact solver verified against brute force; expert bot 0 illegal moves / 0 false accusations (gamble off) across all tournaments

## Tech stack & why
Python 3.11+ (fast to iterate, best LLM SDK ecosystem, ~0.3 s per simulated 4-player game), **Pydantic v2**
for every schema (state/actions/events validate themselves and serialise to JSON for replays), **Typer +
Rich** CLI, **Textual** TUI (same Rich rendering, async, mouse support, headless testable via `App.run_test`), **PyYAML** config, **httpx** direct REST calls (no vendor SDK lock-in; OpenAI-compatible format
covers OpenRouter, OpenAI, Ollama, vLLM, LM Studio), **pytest / ruff / mypy**. **Web UI**: FastAPI + WebSocket backend (`clue/web`, optional extra) and a React + Vite +
TypeScript SPA (`web/`), prebuilt into the package so it runs without node; the same `Request`/queue human-agent
pattern and `run_game(stop=, autosave=)` loop as the TUI, with all redaction done server-side per link token (see
`docs/web.md`).

### Add a new LLM provider
Implement `complete(system, messages, temperature) -> LLMResponse` (see `OpenAICompatibleClient`,
`AnthropicClient` in `clue/agents/llm_client.py`) and add a branch in `make_client`. Select with
`CLUE_LLM_PROVIDER=<name>` in `.env` or `--provider`.

### Add a new strategy
Create `strategies/my_style.md` with: name, description, when-to-use, DO / DON'T lists, example reasoning.
Use it via `--players llm:strategies/my_style.md`, `--strategy strategies/my_style.md`, or `strategy:` in YAML.
Strategies can only influence the model's *choice among legal actions*.

### Add a new agent
Subclass `clue.agents.base.PlayerAgent`, implement `choose_action` and `choose_card_to_show`, register it in
`clue/agents/factory.py`.

## Known simplifications
- Hybrid board: exact 24×25 corridor grid, doors, start squares and passages, but rooms are single nodes (no
  interior squares) — door *approach* squares can be blocked, room capacity is unlimited.
- If a roll cannot be used in full (boxed in), the furthest reachable squares are offered; if none, the turn
  passes (rulebook is silent).
- `solution_probabilities` is a Monte-Carlo approximation; `get_possible_solutions` is exact w.r.t. the
  per-player constraints it checks (has-one-of / not-held / hand-size pigeonhole).

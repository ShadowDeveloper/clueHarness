# Configuration reference

## `game.yaml`
```yaml
edition: classic-clue-2002      # see table
seed: 42                        # int; drives deal, dice, bot RNG
dice: 2                         # 1 | 2 (defaults from edition)
deal_remainder: uneven          # uneven (official) | faceup (house rule)
max_turns: 400                  # safety cap -> draw
ponder: false                   # parallel thinking for AI seats (docs/pondering.md)
workers: 1                      # tournament: games played concurrently (0 = all CPU cores)
players:                        # 3–6 entries, seated in order (Scarlet first)
  - id: P1                      # optional; defaults to P<n>
    kind: human                 # human | llm | baseline
    name: You
  - id: P2
    kind: llm
    model: openai/gpt-4o-mini   # provider model id; "mock" = offline
    strategy: bayesian          # alias, or path to any .md
    temperature: 0.2
    tools: true                 # false = no-tools ablation for this seat
  - id: P3
    kind: baseline
    bot: heuristic              # heuristic | random | expert
```

| `edition` value | Effect |
|---|---|
| `classic-clue-1996` | Classic names, **1 die** |
| `classic-clue-2002` / `classic` | Classic names, **2 dice** (default) |
| `modern` / `modern-2016` | Mrs. White → Dr. Orchid, 2 dice |

Loader: `clue/config.py: load_yaml_config(path) -> (GameConfig, [PlayerSpec], seed, raw)`.
Schema objects: `clue.rules.GameConfig`, `clue.manager.PlayerSpec` (Pydantic; unknown keys are rejected).

## `--players` shorthand
Comma-separated seats, in seating order:

| Token | Meaning |
|---|---|
| `human` | interactive seat |
| `baseline` / `baseline:heuristic` | deduction bot |
| `baseline:random` | random legal moves, 2 % random accusations |
| `baseline:expert` | strongest offline bot: exact assignment-counting solver, expected-information-gain suggestions (exact re-solve per outcome), BFS room targeting, min-leak card showing; deterministic per seed |
| `llm` | LLM, base prompt only, tools on, model from `.env` |
| `llm:<strategy>` | strategy alias or `.md` path |
| `llm:<strategy>:<model>` | explicit model id |
| `llm:<strategy>:notools` or `llm:none:notools` | tools disabled for this seat |

Strategy aliases: `conservative`, `aggressive`, `bayesian`, `info_value_hunter` (`info`), `deceptive`,
`room_rusher` (`rusher`). Anything else is treated as a path (bare names are also looked up in
`strategies/`).

## CLI
```
python -m clue play        [--config F | --players LIST] [--seed N] [--dice 1|2] [--strategy F]
                           [--no-tools] [--provider P] [--ui auto|tui|cli] [--spectate] [--delay S]
                           [--no-emoji] [--ponder] [--ponder-grace S] [--replay-dir D] [--quiet]
                           [--save F] [--no-autosave] [--max-usd X]
python -m clue play        --resume F [--ui ...] [--delay S] [--ponder] [--provider P] [--replay-dir D]
python -m clue tournament  --games N [--config F | --players LIST] [--seed N] [--dice 1|2] [--no-tools]
                           [--provider P] [--report elo.csv] [--replay-dir D] [--ponder] [--workers N|0]
python -m clue eval        [--games N] [--seed N] [--out DIR] [--live]
python -m clue replay      PATH [--viewer Pn] [--tui]
python -m clue web         [--host H] [--port N] [--hotseat] [--open] [--saves-dir D] [--replay-dir D] [--max-usd X] [--dev-origin URL]
```
* `--strategy F` applies `F` to every LLM seat that has no strategy of its own.
* `--no-tools` flips `tools: false` for all LLM seats (ablation).
* `--provider` overrides `CLUE_LLM_PROVIDER` for this run.
* `--ponder` lets idle AI seats think in parallel between turns (see `pondering.md`); `--ponder-grace` bounds the wait when their turn begins.
* `--save F` checkpoints the game after every action; `--resume F` continues it (players/seed/rules come from the file, so
  `--players`/`--config`/`--seed` are ignored). The TUI autosaves to `saves/game_<seed>.json` unless `--no-autosave`. See `playing.md`.
* `--ui auto` = TUI when a human seat exists or `--spectate` is given, plain text otherwise.
* `tournament --report X.csv` also writes `X.json` with per-game results.

## Environment (`.env`)
```
CLUE_LLM_PROVIDER=openrouter        # mock | openrouter | openai | local | anthropic
CLUE_LLM_MODEL=openai/gpt-4o-mini   # default model when a seat has none
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1     # optional
OPENAI_API_KEY=...
OPENAI_BASE_URL=http://localhost:11434/v1            # for provider=local (Ollama default)
LOCAL_API_KEY=ollama                                 # some local servers require any non-empty key
ANTHROPIC_API_KEY=...
```
Loaded with `python-dotenv` on first client construction. No key is ever read from code or config files.
Anything with `model: mock` (or provider `mock`) is fully offline.

| Provider | Endpoint format | Notes |
|---|---|---|
| `openrouter` | OpenAI chat-completions | Any OpenRouter model id (`anthropic/claude-3.5-sonnet`, `openai/gpt-4o`, …) |
| `openai` | OpenAI chat-completions | `OPENAI_BASE_URL` overridable (Azure-style gateways) |
| `local` | OpenAI chat-completions | Ollama, vLLM, LM Studio, llama.cpp server |
| `anthropic` | Messages API | Direct |
| `mock` | — | Follows the tool recommendation; `garbage_rate` / `fail_first` for testing |

## Precedence
CLI flag > YAML key > `.env` > built-in default.

## LLM tool modes & prompt profiles

| flag / token | effect |
|---|---|
| `--tool-mode precomputed` (default) | symbolic `analysis` bundle (posterior, certain facts, opponent threat, top suggestions, recommended action) is injected into the prompt |
| `--tool-mode native` / `llm:<strat>:native` | the model additionally calls tools itself via OpenAI function calling (`TOOL_SPECS`), up to 4 rounds per decision; the final reply is forced to JSON mode |
| `--tool-mode none` / `:notools` | ablation: no analysis, no tools |
| `--prompt-profile compact` / `:compact` | drops most of `public_history` and bookkeeping counters (the notebook + analysis already summarise them) — ~35 % fewer prompt tokens |
| `--max-usd X` | hard cap on live spend for the run (`BudgetExceeded` stops the tournament; usage is printed at exit) |

Live hardening (`clue/agents/llm_client.py`): exponential backoff (4 retries) on 429/5xx/timeouts, per-call
timeout, automatic JSON-mode fallback for providers that reject `response_format`, on-disk response cache
(`CLUE_LLM_CACHE`) keyed by the full request, and per-model cost accounting (OpenRouter's reported `cost` when
available, else a built-in price table). Measured: gpt-4o-mini, native+compact, 3-player game ≈ 40 calls,
~110k prompt tokens, **≈ $0.02 per game**.

## Parallel tournaments

`clue tournament --workers N` (or `-w N`, YAML `workers:`) plays up to N games at the same time; `0` means one per
CPU core. The default is 1 (sequential). `clue live-eval --workers N` does the same per bracket.

* **Offline / mock seats** → a *process* pool: the expert bot and solver are CPU-bound, so this scales with cores
  (2-core sandbox, 8 games of expert vs 2 heuristics: 18.3 s → 10.1 s).
* **Live LLM seats** (or an explicit shared `client=`) → a *thread* pool: games are HTTP-bound, and the one
  process keeps the spend cap (`CostTracker`, lock-protected), the on-disk response cache (atomic writes) and the
  cost report shared. `--max-usd` therefore still caps the *whole* run; when it trips, unfinished games are
  cancelled and the partial results written so far are kept.

Results are identical to a sequential run whatever `workers` is: game *i* is always seeded `seed + i`, and records
are aggregated in seed order even when games finish out of order (asserted by
`test_parallel_tournament_matches_sequential` and `test_parallel_tournament_threads_with_shared_client_and_all_cores`).
Progress lines print as games finish. Note: `--ponder` already uses one background thread per idle seat inside a
game, so with many workers the total thread count is `workers × seats`.

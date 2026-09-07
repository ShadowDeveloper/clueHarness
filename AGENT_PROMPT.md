# Agent Prompt: Build an AI Harness That Can Play Clue / Cluedo

## ROLE
You are an expert game-systems + AI engineer. Build a modular AI harness for playing Classic US Clue (3-6 players).


Before you write any plans or code, ask questions first about any ambiguity in rules, scope, UX, evaluation, etc. List your assumptions for anything you proceed with.

## 1. GOAL
Build a complete, testable system where a user can:
1. Assign any seat at the table to be a Human, an LLM AI, or a scripted baseline bot
2. Optionally attach a separate STRATEGY PROMPT to any AI (e.g. aggressive, Bayesian, deceptive)
3. Play full games: Human vs AI, AI vs AI, Human vs Human, and batch tournaments AI vs AI
4. Trust that rules are enforced correctly and game state is fully auditable/replayable

Core principle: **Separate mechanisms.** Do NOT entangle these 4 layers:
A) Rules Engine (pure logic)
B) Game State Manager (orchestration)
C) Agent Interface + Base Agent Prompts (how to play)
D) Strategy Prompt Layer (how to play *well* / with style)

## 2. ARCHITECTURE - 4 SEPARATE MECHANISMS (REQUIRED)

### A) Rules Engine - `rules/`
Pure, deterministic, no LLM calls, no I/O, fully unit-tested.
Must implement Classic US Clue:
- Cards: 6 Suspects [Miss Scarlet, Col. Mustard, Mrs. White, Mr. Green, Mrs. Peacock, Prof. Plum], 6 Weapons [Candlestick, Dagger, Lead Pipe, Revolver, Rope, Wrench], 9 Rooms [Hall, Lounge, Dining Room, Kitchen, Ballroom, Conservatory, Billiard Room, Library, Study]
  - Add config flag for modern edition where Mrs. White -> Dr. Orchid, but default to Classic.
- Envelope: 1 suspect + 1 weapon + 1 room, hidden.
- Deal remaining 18 cards evenly; if uneven, deal face-up public cards per official rules and document it.
- Board: standard Clue grid with start squares, walls, doors, secret passages: Lounge <-> Conservatory, Kitchen <-> Study. Implement legal movement via dice roll (1d6, or 2d6 option flag).
- Turn flow:
  1. Roll/move OR take secret passage if able
  2. If in room: MAY make Suggestion (current room + any suspect + any weapon, move those tokens into room)
  3. Suggestion is disproved clockwise by first player who CAN show exactly one card; if multiple, holder chooses which to show (privately to suggester only)
  4. MAY make Accusation on your turn (any room/suspect/weapon, ideally in center/hall pool per edition - pick one and document). If correct -> win immediately. If wrong -> eliminated from moving/suggesting/accusing but STILL must disprove when asked. Document your elimination rule to match Hasbro.
- Also support: staying in room to accuse without moving, blocking via token occupancy, no revisiting same room without leaving? Verify against official Hasbro PDF and cite which edition you followed.

Expose pure functions like:
`new_game(config) -> state`, `legal_actions(state, player) -> list`, `apply_action(state, action) -> new_state, events`, `check_winner(state)`

No hidden game-breaking bugs allowed: illegal moves/suggestions/accusations must be rejected with clear errors.

### B) Game State Manager - `manager/`
Stateful orchestrator that uses the Rules Engine but adds:
- Turn order, dice, player elimination, win detection
- Private hands vs public history vs per-player observations
- Suggestion/disproof privacy: shown card visible ONLY to suggester + holder in logs, others see only "disproved by X" or "no one could disprove"
- Full event log + JSONL replay: every roll, move, suggestion, disproof (with redacted + unredacted views), accusation, elimination
- Save/load game, seedable RNG for reproducibility, run N-game tournaments
- Human I/O adapter (CLI first, web UI optional) + AI adapter (same interface)

Must provide: `GameManager.create(players, seed)`, `manager.step(action)`, `manager.get_observation(player_id)`, `manager.export_replay()`

### C) Agent Interface + Base Agent Prompts - `agents/`
Unified interface all players implement:
```python
class PlayerAgent:
  id: str
  kind: str # "human" | "llm" | "baseline"
  def choose_action(observation: dict, legal_actions: list) -> Action
  def choose_card_to_show(observation: dict, cards_that_can_disprove: list) -> Card
```

Observation schema (JSON) must include:
- `you`: id, hand (private), position, eliminated?
- `board`: token positions, your legal moves
- `public_history`: all public events (with private disproofs redacted unless you were involved)
- `notebook`: auto-maintained public knowledge (who showed / couldn't show, disproof counts) - NOT the solution
- `legal_actions`: enumerated from Rules Engine
- `config`: edition, scoring, repeat rules

Provide:
1. `BaselineRandomBot` and `BaselineHeuristicBot` (simple deduction, no LLM) for testing/eval
2. `LLMPlayerAgent` base system prompt that:
   - Explains Clue rules briefly, observation format, and MUST return valid JSON Action only
   - Enforces: never hallucinate cards, never take illegal action, always use tools for math, update notebook via tool
   - Handles 2 decision types: main action + which card to reveal when disproving

LLM agent MUST support provider-agnostic config: OpenAI / Anthropic / local model via env vars + mock LLM for offline tests.

### D) Strategy Prompt Layer - `strategies/`
Pluggable extra system-prompt fragments appended to the Base Agent Prompt WITHOUT changing base logic.
User can assign: `Player2 = LLM(gpt-4o) + strategy/bayesian_info_max.md`

Ship at least 6 strategies as separate .md files:
1. `conservative_notebook.md` - never accuse below ~90% certainty
2. `aggressive_accuser.md` - accuse early on educated guesses
3. `bayesian_probabilist.md` - explicitly reason over remaining combos
4. `info_value_hunter.md` - maximize expected information gain per suggestion
5. `deceptive_misdirector.md` - when choosing which card to show, prefer misleading holder patterns; vary suggestions to hide hand
6. `room_rusher.md` - prioritize board control, passages, high-traffic rooms

Each strategy file must have: name, description, when-to-use, DO/DON'T list, and example reasoning snippet.

Allow custom user strategies via: `--strategy path/to/my_style.md` or config YAML.

## 3. PLAYER ASSIGNMENT SYSTEM (REQUIRED)
User must be able to assign AIs + strategies per seat via BOTH config file and CLI.

Example `game.yaml`:
```yaml
edition: classic-clue-1996
seed: 42
players:
  - id: P1
    kind: human
    name: You
  - id: P2
    kind: llm
    model: gpt-4o
    strategy: strategies/bayesian_probabilist.md
    temperature: 0.2
  - id: P3
    kind: llm
    model: claude-sonnet
    strategy: strategies/deceptive_misdirector.md
  - id: P4
    kind: baseline
    bot: heuristic
```

CLI examples you must support:
`python -m clue play --config game.yaml`
`python -m clue play --players human,llm:bayesian,llm:aggressive,baseline`
`python -m clue tournament --games 100 --players llm:bayesian,llm:info_value_hunter,baseline,baseline --seed 123 --report elo.csv`

## 4. LLM + SYMBOLIC / MATH TOOLS (REQUIRED - NOT PURE LLM GUESSING)
LLM agents get structured tools. They MUST call tools for deduction, not vibes.

Implement at least these tools (as functions the LLM can call, or as pre-computed observation fields + callable helpers):
- `get_unseen_cards(player_id)` - cards not in your hand and not seen
- `get_possible_solutions(notebook)` - all remaining [suspect, weapon, room] combos consistent with observations
- `solution_probabilities(notebook)` - Bayesian-ish posterior over combos given disproof history
- `suggestion_ev(suspect, weapon, room)` - expected information gain: how many opponents could disprove, novelty score
- `update_notebook(event)` - append structured deduction: e.g. "P3 showed a card for [Plum, Rope, Hall] -> P3 has >=1 of those"
- `can_accuse_confidently(threshold)` - returns best guess + confidence

Add more tools if they would add value to the system.

Log all tool calls in replay for audit. Provide a `--no-tools` ablation flag to prove tools help (for eval report).

## 5. MODES OF PLAY + EVAL
- Interactive single game with rich CLI display of board (ASCII), hand, notebook, history
- Batch tournament runner with stats: win_rate by agent/strategy, avg_turns_to_win, false_accusation_rate, avg_suggestions_per_game, ELO
- `eval/` script that runs Baseline vs Heuristic vs LLM+tools vs LLM no-tools and writes `report.md + charts.png`
- Replays: `replays/game_<seed>.jsonl` + `replays/game_<seed>_redacted_P2.json` to verify privacy

## 6. TECH STACK - YOU DECIDE (JUSTIFY IT)
No fixed stack. Choose the best tool for maintainability + AI + sim speed. Default recommendation if unsure: Python 3.11+ for engine/manager/agents/eval, Pydantic for schemas, pytest, Typer/Click for CLI, YAML config, pluggable LLM client (LiteLLM-style). Web UI optional: FastAPI + minimal frontend only AFTER CLI works.

Document your choice in README: why this stack, how to add new LLM provider, how to add new strategy.

## 7. DELIVERABLES
```
/README.md - setup, rules edition cited, how to play, how to add strategy/agent
/rules/ + tests/test_rules.py - 95%+ coverage on movement, suggestion, disproof order, accusation, elimination, passages
/manager/ + tests/test_manager.py - privacy tests (no leakage), replay determinism with same seed
/agents/base_prompt.md + llm_client.py + baselines.py
/strategies/*.md (6+ files)
/eval/tournament.py + report example
game.yaml example + demo transcript demo_game.md
```

## 8. ACCEPTANCE CRITERIA
- [ ] Can play full 4-player Classic game Human + 3 AI to completion with zero illegal moves
- [ ] Privacy: from redacted log, non-involved player cannot infer shown card beyond "disproved"
- [ ] Determinism: same seed + same scripted actions = identical replay hash
- [ ] LLM returns valid Action JSON 99%+ of time; invalid -> 1 retry with error feedback, then fallback to heuristic bot (log it)
- [ ] Strategy swapping changes behavior measurably (tournament win-rate / accusation timing differs, documented)
- [ ] Tools ablation: LLM+tools beats LLM no-tools on win-rate OR false-accusation rate in 50-game eval (or explain why not)
- [ ] `pytest` passes, `ruff`/`mypy` (or equivalent) clean, README has 5-min quickstart

## 9. BUILD STEPS
1. Ask questions first, then lock Classic rules spec in `RULES_SPEC.md` with Hasbro source + all edge-case decisions
2. Implement Rules Engine + exhaustive unit tests
3. Implement Game State Manager + privacy + replay + determinism tests
4. Implement Agent Interface + baselines + observation serializer
5. Implement LLM client (mock first) + base prompt + JSON validation + retry/fallback
6. Implement math tools + notebook updater
7. Implement Strategy layer + assignment config + CLI
8. Implement tournament + eval + demo game transcript
9. Final polish: README, type hints, lint, coverage report

## 10. CONSTRAINTS
- Rules Engine must NEVER import LLM code. Manager must NEVER contain strategy text. Strategies must NEVER change legal_actions.
- All LLM reasoning must be logged, but final Action must validate against `legal_actions`.
- No hard-coded API keys. Use `.env`. Must run fully offline with `--players baseline,baseline,baseline` and mock LLM.
- Keep files small and modular. Prefer explicit schemas over free text.

## 11. NOW DO THIS
1. Ask questions first - output your top 10 clarifying questions grouped by Rules / UX / LLM / Eval, then propose defaults and wait for answers if interactive, otherwise proceed with defaults clearly marked [ASSUMED].
2. Then scaffold repo, implement in order in Section 9, and demo a 4-player game.

Ask questions first - do not skip step 1.
---

This prompt is located at `/AGENT_PROMPT.md`

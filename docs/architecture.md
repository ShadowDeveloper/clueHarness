# Architecture

## The four mechanisms
```
             ┌──────────────────────────────────────────────────────────────┐
             │ D  strategies/*.md   (text only, appended to the base prompt) │
             └───────────────▲──────────────────────────────────────────────┘
                             │ read by
┌──────────────┐   ┌─────────┴──────────┐   ┌──────────────┐
│ C  agents/   │   │ agents/llm_agent   │   │ tools/       │  symbolic deduction
│  PlayerAgent │◄──┤ LLMPlayerAgent     ├──►│ deduction.py │  (pure functions over Notebook)
│  baselines   │   │ llm_client (REST)  │   └──────────────┘
│  human / tui │   └────────────────────┘
└──────▲───────┘
       │ choose_action(obs, legal) / choose_card_to_show(obs, cards)
┌──────┴───────────────────────────────────────────────────────────────┐
│ B  manager/   GameManager (seeded RNG, event log, per-player Notebook,│
│               observations, redaction, replay, save/load)            │
│               runner.run_game (validation, retry, fallback)          │
└──────▲───────────────────────────────────────────────────────────────┘
       │ new_game / legal_actions / apply_action / is_legal
┌──────┴───────────────────────────────────────────────────────────────┐
│ A  rules/     cards · board · state (Pydantic) · engine (pure)        │
└──────────────────────────────────────────────────────────────────────┘
```

### Import rules (enforced by review + `grep` in CI-style check)
* `clue.rules` imports only `clue.rules`. No I/O, no randomness except the `random.Random` passed in.
* `clue.manager` imports `clue.rules` and the abstract `clue.agents.base.PlayerAgent` (runner only). It has
  no knowledge of strategies beyond the opaque `PlayerSpec.strategy` path stored for labelling/replays.
* Core inference modules in `clue.tools` use `clue.manager.notebook` (data) and `clue.rules.cards`; the optional
  `coach.py` UI helper also adapts a live `GameManager`/`Action` for human coaching.
* `clue.agents` may import everything below it. `clue.tui` imports agents + manager.
* Strategies are data. Nothing in code branches on strategy content.

## Data flow of one decision
1. `run_game` asks the manager who acts (`acting_player()`: disprover during `disprove`, else current).
2. `gm.get_observation(pid)` builds the redacted view (see `observation_schema.md`) and
   `gm.legal_actions(pid, include_accusations=False)` enumerates concrete actions; accusation combinations are
   validated structurally via `can_accuse` / `is_legal` instead of enumerated (the family size depends on the edition's card lists).
3. The agent returns an `Action`. `LLMPlayerAgent` first runs the tool bundle, prompts, parses, validates.
4. The runner re-validates with `rules.is_legal`. Invalid → logged `illegal_action`, the observation gets a
   `last_error`, one retry; still invalid → a safe fallback action (`end_turn`/`roll`/first move/first card)
   is applied and logged as `fallback_action`.
5. `gm.step(action)` → `rules.apply_action` returns `(new_state, events)`; the manager appends the action
   and events to the log and feeds each event, redacted per viewer, into every player's `Notebook`.
6. Agents' `on_event` hooks and the UI callback receive the events.

## Key types (`clue/rules/state.py`)
| Type | Purpose |
|---|---|
| `GameConfig` | edition, dice, deal_remainder, num_players, max_turns, teams, private_disproofs, wrong_accusation, accusation_penalty_turns, shuffle_seats |
| `PlayerState` | id, seat, hand, position, eliminated, may_suggest, left_room |
| `GameState` | players, solution, token/weapon positions, current, phase, roll, pending_suggestion, disprover_index, winner, finished |
| `Action` | `type ∈ {roll, move, passage, suggest, accuse, show_card, end_turn}` + fields; `key()` gives a stable label |
| `Event` | `type`, `turn`, `player`, `public{}`, `private{}`, `private_to[]`; `redacted_for(viewer)` |
| `IllegalAction` | raised by `apply_action` |

Phases: `move → (suggest | accuse) → [disprove] → accuse → end`. `legal_actions` is the single source of
truth; `apply_action` never trusts the caller.

## Positions
A position is either a room name (`"Kitchen"`) or `"row,col"`. The board (`rules/board.py`) is a frozen
graph: corridor cell set, door-cell → room map, per-room door list, secret passages, start squares.
`reachable(pos, steps, occupied)` does BFS with blocking and returns exact-distance corridor cells plus
rooms reachable within `steps` (entering ends movement). Results are memoised per `(start, blocked)`.

## Privacy model
Every `Event` carries its sensitive payload in `private` with an explicit `private_to` list. The manager
never hands out raw events: observations and replays go through `redacted_for(viewer)`. Tool calls and
agent notes are stored as `LogRecord`s with `private_to=[player]` and are dropped from other players'
replays. Tests: `tests/test_manager.py::test_no_leak_in_redacted_replay`, `::test_notebook_facts_are_sound`.

## Determinism
`GameManager(seed)` owns one `random.Random`. Dice, deal, and weapon placement come from it; bots receive
their own seeded RNGs from the factory (`seed + seat`). `replay_hash()` is the SHA-256 of the unredacted log,
so *same seed + same agent decisions ⇒ same hash* (`test_same_seed_same_replay_hash`). `save()` persists the
RNG state, so a loaded game continues identically (`test_save_load_roundtrip`).

## Concurrency (ponder mode)
`manager/ponder.py: PonderManager` runs one daemon thread per idle, ponder-capable agent on a deep-copied
observation + snapshot notebook. It interrupts sessions cooperatively (`PonderContext.request_stop`) on
informative events and before the player's own decision, joins with a bounded grace period, merges notes on
the manager thread, and logs a private `ponder` record. Game state is only ever mutated by the runner thread.
Full description: `pondering.md`.

## Concurrency (TUI)
`run_game` runs in a Textual worker thread. `TUIHumanAgent` blocks that thread on a `queue.Queue` while the
UI thread renders the request; the UI puts the chosen `Action` back. AI seats never block. Spectator pacing
is a sleep in the event callback, so it cannot affect game logic.

## Package map
```
clue/__main__.py      Typer CLI (play / tournament / eval / replay)
clue/config.py        YAML → GameConfig + PlayerSpec
clue/rules/           cards.py board.py state.py engine.py
clue/manager/         game_manager.py notebook.py runner.py ponder.py
clue/tools/           deduction.py
clue/agents/          base.py baselines.py human.py llm_client.py llm_agent.py factory.py base_prompt.md ponder_prompt.md
clue/tui/             app.py (ClueApp, TUIHumanAgent, run_tui)
clue/eval/            tournament.py report.py
eval/                 tournament.py (entry), make_demo.py, make_tui_screenshot.py, report.md, charts.png
tests/                test_rules.py test_manager.py test_tui.py test_ponder.py
```

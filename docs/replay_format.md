# Replay & persistence format

## Files
| File | Produced by | Contents |
|---|---|---|
| `replays/game_<seed>.jsonl` | `play`, `tournament --replay-dir` | **Unredacted** ("God view"): one `LogRecord` per line |
| `replays/game_<seed>_redacted_<Pn>.json` | `play` | The same log as player *Pn* is allowed to see |
| `<path>.json` via `GameManager.save()` | API | Full checkpoint (state, RNG state, log) for `GameManager.load()` |
| `elo.csv` / `elo.json` | `tournament` | Aggregate table / per-game results |

## Record kinds
Every line has `seq` (0-based, contiguous) and `kind`.

### `event` — emitted by the rules engine or manager
```json
{"seq": 10, "kind": "event", "type": "disproved", "turn": 0, "player": "P2",
 "suggester": "P1", "disprover": "P2", "card": "Rope"}
```
| `type` | Public fields | Private fields (`private_to`) |
|---|---|---|
| `game_start` | seed, players (specs), config, faceup | `solution`, `hands` (nobody — God view only) |
| `turn_start` | player, turn | |
| `roll` | dice[], total | |
| `boxed_in` | | |
| `move` / `passage` | from, to | |
| `suggest` | suspect, weapon, room | |
| `cannot_disprove` | suggester | |
| `can_disprove` | suggester | |
| `disproved` | suggester, disprover | `card` (suggester, disprover) |
| `no_one_disproved` | suspect, weapon, room | |
| `accuse` | suspect, weapon, room, correct | |
| `eliminated` | | |
| `game_over` | winner (or null), solution, reason? | |

### `action` — the validated action that produced the following events
```json
{"seq": 9, "kind": "action", "type": "show_card", "player": "P2", "card": "Rope"}
```
Actions are public in the God view. In a redacted view `show_card` actions are still listed (the *fact* of
disproving is public) but the `card` field is removed unless the viewer was involved.

> Note: action records are visible to all viewers *except* their private `card`. Implementation:
> `GameManager.step` stores the action; `export_replay(viewer)` strips `card` from `show_card` actions when
> the viewer is neither the suggester nor the shower.

### `tool_call` — symbolic tool invocation by an LLM agent (private to that player)
```json
{"seq": 31, "kind": "tool_call", "player": "P2", "tool": "solution_probabilities", "args": {},
 "result": {"n_possible": 84, "best": ["Prof. Plum", "Rope", "Study"], "best_prob": 0.03, "...": "..."}}
```

### `ponder` — one background-thinking session (private)
```json
{"seq": 40, "kind": "ponder", "player": "P2", "stopped_by": "new_information", "duration_ms": 41,
 "trigger": "step", "tool_calls": 2, "rounds": 1, "notes": ["…"], "result": {"plan": "…"}, "error": null}
```
Tool calls made while pondering carry `"during": "ponder"` in `args`. See `pondering.md`.

### `agent_note` — agent-side audit trail (private)
`summary ∈ llm_response | llm_error | illegal_action | fallback_action | fallback_to_heuristic | fallback_card`
with the raw model text (truncated to 4 000 chars), token usage, errors, or the substituted action.

## Redaction rules
1. `private` fields are merged into a record only for viewers listed in `private_to`.
2. `tool_call` / `agent_note` / `ponder` records of other players are **omitted entirely**.
3. `game_start` loses `solution` and `hands` for every real viewer.
4. Nothing else changes: `seq` numbers are preserved so redacted and full logs can be joined.

Verification: `tests/test_manager.py::test_no_leak_in_redacted_replay` and the excerpt at the end of
`demo_game.md`.

## Determinism hash
`GameManager.replay_hash()` = SHA-256 of `json.dumps(export_replay(None), sort_keys=True)`.
The same seed, same seating and identically-seeded agents reproduce it byte for byte
(`test_same_seed_same_replay_hash`). LLM agents with a live model are *not* deterministic; their replay is
still fully auditable via `agent_note` records.

## Checkpoints
`save()` writes `{seed, rng (Mersenne state), config, specs, state, events, log, action_count}`.
`load()` rebuilds the manager and re-derives all notebooks by replaying the events, so notebooks can never
drift from the log.

## Reading replays
```
python -m clue replay replays/game_42.jsonl              # God view, pretty-printed
python -m clue replay replays/game_42.jsonl --viewer P3  # (pretty-printer only; redaction is in the *_redacted files)
jq 'select(.type=="accuse")' replays/game_42.jsonl
```

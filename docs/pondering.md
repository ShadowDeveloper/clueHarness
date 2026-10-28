# Parallel thinking ("ponder" mode)

In real Clue everybody keeps working on their notebook while the others move. `--ponder` gives AI seats the
same ability: while it is not their turn they run a background *ponder session* in which they may reason,
call the symbolic tools and record deductions — and they are **interrupted gracefully** the moment new
information arrives or their own turn begins. The idea mirrors the UCI `ponder` flag in chess engines.

```
python -m clue play --players llm:bayesian,llm:info,baseline,baseline --spectate --ponder
python -m clue tournament --games 50 --players llm:bayesian,baseline,baseline --ponder
```
YAML: `ponder: true` at the top level. Tuning: `--ponder-grace SECONDS` (default 2.0).

## Lifecycle
```
             step applied
                  │
                  ▼
   ┌─── PonderManager.on_events ───────────────────────────────────────┐
   │ informative event? (suggest / disproof / no-one / accuse / elim)   │
   │   yes → request_stop("new_information") on every idle session     │
   │ reap finished sessions → merge notes → write `ponder` log record   │
   │ start a session for every idle, eligible player lacking one       │
   └────────────────────────────────────────────────────────────────────┘
                  │
                  ▼  (next player's decision)
   PonderManager.before_decision(pid)
     request_stop("your_turn") → join(grace) → merge → summary handed to choose_action
     if still running after `grace` → orphaned; merged later when it lands (never blocks)
```
Eligible = agent sets `supports_ponder = True`, is not eliminated, game not over. A player who finished a
session and got no new information since does **not** restart (so bots don't spin on every dice roll).

## Interrupts are cooperative
A session receives a `PonderContext` and must call `ctx.check()` (or use `ctx.tool()` / `ctx.wait()`, which
check for you) between expensive steps. On stop, `PonderInterrupted(reason)` is raised inside the session;
`reason ∈ new_information | your_turn | superseded | game_over`. Everything noted with `ctx.note()` before the
interrupt is kept. A session that ignores the stop (e.g. a blocking network call) is simply left behind after
`grace` seconds; the game continues, and its notes are merged when it finally returns. The stale thread is a
daemon and costs nothing else.

## Isolation guarantees
* The session gets a **deep copy** of the observation and a **snapshot** `Notebook`; tools run against the
  snapshot. Mutating it cannot affect the live game or other players (`test_ponder_tools_use_snapshot_not_live_state`).
* The only writes back are `ctx.note()` strings, merged (de-duplicated) into that player's `notebook.notes`
  by the manager thread when the session is finalised.
* Pondering cannot produce an action. The real decision is still `choose_action` on a fresh observation; the
  agent merely receives `observation["ponder_summary"]` (`result`, `notes`, `stopped_by`, or `pending`).
* Heuristic bots' decisions are provably unchanged by pondering — the event/action log with and without
  `--ponder` is identical (`test_game_outcome_identical_with_and_without_ponder_for_heuristics`).

## What each agent does while pondering
| Agent | Behaviour |
|---|---|
| `BaselineHeuristicBot` | recomputes candidate solutions, caches a target-room list, and notes single-card / single-candidate deductions; Large-edition candidates are propagation-filtered and may be unverified |
| `LLMPlayerAgent` | bounded loop (≤ 5 rounds) driven by `agents/ponder_prompt.md`: reply with `{"tool": …}` to call a tool or `{"plan": …, "notes": […], "done": true}` to finish. The plan is injected into the next real decision as `your_plan_from_pondering`. Interrupt is checked before and after each LLM call and inside every tool call |
| `MockLLMClient` | offline stand-in: asks for `solution_probabilities`, notes the leading combo, returns a plan |
| `BaselineRandomBot`, humans | `supports_ponder = False` — never scheduled |

## Audit trail
Every session ends with a private `ponder` record:
```json
{"kind": "ponder", "player": "P2", "stopped_by": "new_information", "duration_ms": 41,
 "trigger": "step", "tool_calls": 2, "rounds": 1,
 "notes": ["only one consistent solution left: Prof. Plum / Rope / Study"],
 "result": {"plan": "head for the Study and accuse if still unique"}, "error": null}
```
Tool calls made during a session carry `"during": "ponder"` in their args. Both are visible only to that
player in redacted replays. `GameManager.summary()["ponder"]` and the `play` command print per-player
counters: `sessions`, `tool_calls`, `notes`, `interrupted_by_info`, `interrupted_by_turn`, `grace_timeouts`,
`errors`.

## Writing a pondering agent
```python
class MyBot(PlayerAgent):
    supports_ponder = True

    def ponder(self, observation, ctx):
        post = ctx.tool("solution_probabilities")        # raises PonderInterrupted if stopped
        for step in expensive_reasoning():
            ctx.check()                                   # cooperative interrupt point
        ctx.note("P3 must hold the Lounge")               # persisted to the notebook
        self.cached_plan = ...                            # cache on self for choose_action
        return {"summary": "..."}                         # goes into the ponder log
```
Rules: never touch live state, never block without checking, keep results on `self` or in `ctx.notes`.
Long network calls: check `ctx.stopped` right after they return and discard the result if set.

## Performance
Sessions are OS threads; tools are pure Python. In one historical small-table benchmark, four heuristic seats
increased wall time from roughly 0.4 s to 0.5 s; actual overhead depends on game length and the tools used.
LLM pondering costs extra API calls (observed at roughly one to five per informative event per idle LLM seat).
Use `--ponder` in tournaments only when that time and budget are acceptable.

## Tests
`tests/test_ponder.py`: interrupts by info and by turn, grace timeout non-blocking, snapshot isolation, note
merging, privacy of `ponder`/`tool_call` records, heuristic determinism with/without ponder, mock-LLM loop
producing plans, `PonderContext` API.

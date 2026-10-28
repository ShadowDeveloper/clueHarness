# Evaluation

## Metrics (`python -m clue tournament`, `clue/eval/tournament.py`)
Agents are aggregated by **label** (`kind[:model][:strategy][:no-tools]` or `baseline:<bot>`), so two seats
with the same configuration pool their statistics.

| Column | Definition |
|---|---|
| `games` | seats played with this label (2 identical seats × N games = 2N) |
| `wins` / `win_rate` | correct accusations / games |
| `false_accusation_rate` | games in which the label made a wrong accusation / games |
| `avg_turns_to_win` | mean global turn counter at the winning accusation (lower = faster solver) |
| `avg_suggestions_per_game` | suggestions made / games (tempo / information gathering) |
| `illegal_attempts` | actions rejected by the validator before retry/fallback (should be 0 for bots) |
| `elo` | pairwise winner-vs-each-loser updates, K = 24, start 1000, computed over labels |

Seats are **shuffled per game** with a seed derived from the game seed, so first-mover advantage and
relative seating (who sits after whom, which matters for disproof order) are averaged out. Draws
(`max_turns` reached, everyone eliminated) count as no win for anyone and leave ELO unchanged.

## The eval script (`python -m clue eval`)
Bracket A — tool ablation: `baseline:random`, `baseline:heuristic`, `llm+tools (bayesian)`,
`llm no-tools (bayesian)`.
Bracket B — strategies: conservative vs aggressive vs bayesian vs room_rusher, same model.
Outputs `eval/report.md`, `eval/report.json`, `eval/charts.png`.

### Offline semantics (default)
`MockLLMClient` (2 % deliberately malformed replies to exercise retry/fallback):
* tools on → follows the `recommended_action` from the symbolic layer (i.e. behaves like the heuristic
  policy driven through the full LLM pipeline: prompt building, JSON parsing, validation, logging);
* tools off → emits a random legal action, enters rooms when possible, suggests unseen cards, and accuses
  when only ≤ 2 combos of unseen cards remain or with 3 % probability — a stand-in for "reasoning by vibes".
Hence bracket A measures the tool layer; bracket B is expected to be flat (the mock does not read prompts).

### Live semantics (`--live`)
Uses `.env` provider/model for every LLM seat. Budget estimate: ~45 decisions per LLM seat per game ×
~3 k prompt tokens. 50 games × 2 LLM seats ≈ 4 500 calls per bracket.

## Archived offline benchmark snapshot (50 games/bracket, seed 0)

These values are the checked-in `eval/report.md` snapshot, not a promise that a fresh run will match exactly. Regenerate with `python -m clue eval --games 50 --seed 0`.
| agent | win_rate | false_acc | avg_turns_to_win | sugg/game |
|---|---|---|---|---|
| baseline:heuristic | 0.56 | 0.00 | 68.0 | 34.6 |
| llm(mock)+tools | 0.30 | 0.00 | 59.5 | 35.4 |
| llm(mock) no-tools | 0.04 | 0.86 | 74.0 | 5.5 |
| baseline:random | 0.00 | 0.60 | — | 5.7 |

Reading: with tools the LLM pipeline never false-accuses and wins 30 %; without tools it self-eliminates in
86 % of games. The heuristic edges the tool-driven mock because 2 % of mock replies are garbage (→ safe
fallback that sometimes wastes a turn) and because after a fallback the retry consumes the same
`recommended_action`, so the two are not perfectly identical policies.

## Reproducing
```
python -m clue eval --games 50 --seed 0            # ≈ 2–3 min offline
python -m clue tournament --games 100 --players llm:bayesian,llm:info_value_hunter,baseline,baseline --seed 123 --report elo.csv
```
Determinism: same seed ⇒ same deals, dice and bot choices ⇒ identical tables offline.

## Acceptance evidence
| Criterion | Evidence |
|---|---|
| Full 4-player Human + 3 AI game, zero illegal moves | `demo_game.md` (`illegal attempts = 0`), `tests/test_tui.py::test_human_seat_drives_game_via_option_list` |
| Privacy | `test_no_leak_in_redacted_replay`, `test_observation_hides_other_hands_and_solution`, `replays/game_42_redacted_P3.json` |
| Determinism | `test_same_seed_same_replay_hash`, `test_save_load_roundtrip` |
| JSON validation, retry, and fallback paths | `test_llm_agent_fail_first_then_valid`, `test_llm_agent_retry_then_fallback`; per-game `stats` printout (live rates vary by model) |
| Tools ablation | table above |
| Strategy swapping measurable | labels + `avg_turns_to_win` / `false_accusation_rate` per strategy; requires `--live` |
| Test and static checks | Current results are reported by CI; run the commands in `docs/extending.md` locally |

## Expert bot (Classic benchmark snapshot)

The following archived Classic-edition results compare `baseline:expert` with three `baseline:heuristic` seats,
with seats shuffled per game (fair share = 0.25). The expert uses exact assignment counting only within solver bounds; Large-edition suggestion scoring is approximate.

| variant | games | expert win rate |
|---|---|---|
| marginal-approx suggestion scoring only | 120 | 0.35 |
| + exact re-solve of all 36 suggestions (default) | 120 | 0.40 |

Both variants have a 0 % false-accusation rate (`gamble=False`); the default `gamble=True` only accuses early
when an opponent's unrefuted suggestion equals our top combo. Diagnostic: the expert reaches a unique solution
a median of ~10 turns earlier than a heuristic seat in the same game (`solve()` on every seat's notebook).
Runtime: ~8 s/game with exact re-solving (vs ~1 s/game for the heuristic); set `exact_top=0` for speed.

Opponent-aware gambling (`gamble=True`, default): accuses below certainty only when
`P(best) > (1 - P(a rival wins before my next turn)) * P(I win later)`. On 80 seat-shuffled games it changed
the win rate by +1 game vs `gamble=False` — the heuristic opponents rarely threaten early, so the rule mostly
sits idle; it matters against stronger fields (expert-vs-expert) where the race is tight.

## Statistics (`clue/eval/stats.py`)

Every tournament table now carries a **Wilson 95 % interval** (`win_ci95`), all-pairs **paired sign tests**
over shared seeds (`pairwise`), a **candidate-count curve** (mean solver-reported envelope candidate count at each of the
agent's turn starts, using the agent's own notebook; exact when solver bounds permit, propagation-filtered on Large) and a behavioural
**fingerprint** per label (suggestions, passages, rooms visited, own cards in suggestions, solved rate,
accusation rate, premature-accusation rate = accused while >1 combo remained). Written to `<report>.json`.

## Ponder ablation (offline, mock LLM, 4p: llm + expert + 2×heuristic, 20 paired seeds, seed 500)

| variant | llm wins | expert | heuristic (2 seats) |
|---|---|---|---|
| ponder off | 1/20 [0.01, 0.24] | 13/20 | 6/40 |
| ponder on (797 ponder rounds) | 3/20 [0.05, 0.36] | 13/20 | 4/40 |

Offline the mock's pondering only refreshes the posterior, so the effect is within noise; the live bracket
below measures it with a real model.

## Live evaluation (`python -m clue live-eval`)

`live-eval --model M --games N --max-usd X [--brackets ablation,ponder]` runs, for each variant, the SAME N
seeds vs `baseline:expert` + `baseline:heuristic` (seats shuffled per seed), so variants are directly
paired. Ablation = tool mode precomputed / native / none; ponder = native with ponder off / on. Results are
saved incrementally (`live_*.partial.json`) and summarised in `eval/live/live_report.md`. The checked-in report
is a historical snapshot; rerun `live-eval` for current measurements. It used the free OpenRouter model
`nvidia/nemotron-3-super-120b-a12b:free`; `openrouter/free` itself was unusable in that run because it routed
to reasoning/safety-classifier models that returned no JSON.

### Results (2026-09-06, `nvidia/nemotron-3-super-120b-a12b:free`, 5 paired seeds/variant, compact prompt)

| variant | LLM wins | Wilson 95% | valid JSON 1st try | fallbacks | solved before accusing | premature accusations |
|---|---|---|---|---|---|---|
| precomputed | 1/5 | [0.04, 0.62] | 95.7 % | 1.4 % | 20 % | 0 % |
| native | 0/5 | [0.00, 0.43] | 92.9 % | 1.4 % | 0 % | 0 % |
| none (ablation) | 0/5 | [0.00, 0.43] | **30.8 %** | 12.5 % | 0 % | **60 %** |
| native + ponder | 2/5 | [0.09, 0.70] | — | — | 40 % | 0 % |

Opponent `baseline:expert` won 4/5 in every bracket. Take-aways at this sample size: (1) the tool layer is what
keeps the LLM legal and patient — without it the model guessed early in 3 of 5 games; (2) native function
calling did not beat the precomputed bundle for this model (it called tools 3×/game and used 40 % more
tokens); (3) pondering produced the best LLM result and the steepest late-game candidate curve
(4.0 combos at turn 7 vs 8.7 without), but 5 games cannot separate it from noise (sign test p > 0.3).
The identical "native" rows in both brackets come from the response cache (same seeds + same prompts →
same games), which doubles as a determinism check. Total live spend for the whole project so far: $0.075.

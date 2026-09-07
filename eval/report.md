# Clue harness evaluation report
Games per bracket: **50**, base seed 0, mode: **OFFLINE (MockLLM)**.

## Bracket A — Random vs Heuristic vs LLM+tools vs LLM no-tools
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:heuristic | 50 | 28 | 0.56 | 0.0 | 68.0 | 34.62 | 0 | 1261 |
| llm:mock:bayesian_probabilist | 50 | 15 | 0.3 | 0.0 | 59.5 | 35.36 | 0 | 1093 |
| llm:mock:bayesian_probabilist:no-tools | 50 | 2 | 0.04 | 0.86 | 74 | 5.52 | 0 | 869 |
| baseline:random | 50 | 0 | 0.0 | 0.6 | None | 5.66 | 0 | 777 |

## Bracket B — Strategy comparison (same model, different strategy prompts)
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| llm:mock:aggressive_accuser | 50 | 16 | 0.32 | 0.0 | 44.6 | 11.16 | 0 | 1085 |
| llm:mock:conservative_notebook | 50 | 16 | 0.32 | 0.0 | 53.4 | 11.22 | 0 | 1050 |
| llm:mock:room_rusher | 50 | 11 | 0.22 | 0.0 | 48 | 11.08 | 0 | 960 |
| llm:mock:bayesian_probabilist | 50 | 7 | 0.14 | 0.0 | 53.9 | 10.98 | 0 | 905 |

## Notes
- In OFFLINE mode the MockLLM follows the symbolic `recommended_action` when tools are on, and plays an unguided legal action otherwise; the ablation therefore measures the value of the tool layer, not of any particular model. Strategy prompts only change behaviour when a real LLM reads them, so bracket B is expected to be flat offline — run with `--live` to measure strategy effects.
- `false_accusation_rate` = fraction of games in which the agent made a wrong accusation.
- ELO uses pairwise winner-vs-loser updates (K=24) starting at 1000.
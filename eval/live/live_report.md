# Live evaluation — `nvidia/nemotron-3-super-120b-a12b:free`
5 paired seeds per variant, 3 players (LLM vs baseline:expert + baseline:heuristic, seats shuffled per seed).

## Bracket: ablation
| variant | games | wins | win rate [Wilson 95%] | valid JSON 1st try | fallbacks | tool calls/game | ponder rounds/game | prompt tok/game | $/game |
|---|---|---|---|---|---|---|---|---|---|
| precomputed | 5 | 1 | 0.20 [0.04, 0.62] | 0.957 | 0.014 | 0.0 | 0.0 | 74417 | 0.0 |
| native | 5 | 0 | 0.00 [0.00, 0.43] | 0.929 | 0.014 | 3.0 | 0.0 | 106220 | 0.0 |
| none | 5 | 0 | 0.00 [0.00, 0.43] | 0.308 | 0.125 | 0.0 | 0.0 | 50537 | 0.0 |

Per-seed winners (paired): precomputed, native, none
| seed | precomputed | native | none |
|---|---|---|---|
| 0 | expert | expert | expert |
| 1 | expert | expert | heuristic |
| 2 | expert | expert | expert |
| 3 | **LLM** | heuristic | heuristic |
| 4 | expert | expert | expert |

Full table — precomputed:
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:expert | 5 | 4 | 0.8 [0.376, 0.964] | 0.2 | 20.8 | 6.4 | 0 | 1068 |
| llm:nvidia/nemotron-3-super-120b-a12b:free:bayesian_probabilist:compact | 5 | 1 | 0.2 [0.036, 0.624] | 0.0 | 27 | 7.0 | 0 | 985 |
| baseline:heuristic | 5 | 0 | 0.0 [0.0, 0.434] | 0.0 | None | 7.2 | 0 | 948 |

Full table — native:
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:expert | 5 | 4 | 0.8 [0.376, 0.964] | 0.2 | 21.5 | 6.8 | 0 | 1067 |
| baseline:heuristic | 5 | 1 | 0.2 [0.036, 0.624] | 0.0 | 25 | 7.0 | 0 | 985 |
| llm:nvidia/nemotron-3-super-120b-a12b:free:bayesian_probabilist:native:compact | 5 | 0 | 0.0 [0.0, 0.434] | 0.0 | None | 7.0 | 0 | 948 |

Full table — none:
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:expert | 5 | 3 | 0.6 [0.231, 0.882] | 0.0 | 19.7 | 6.8 | 0 | 1041 |
| baseline:heuristic | 5 | 2 | 0.4 [0.118, 0.769] | 0.0 | 15 | 6.6 | 0 | 1013 |
| llm:nvidia/nemotron-3-super-120b-a12b:free:bayesian_probabilist:no-tools:compact | 5 | 0 | 0.0 [0.0, 0.434] | 0.6 | None | 2.8 | 0 | 946 |

## Bracket: ponder
| variant | games | wins | win rate [Wilson 95%] | valid JSON 1st try | fallbacks | tool calls/game | ponder rounds/game | prompt tok/game | $/game |
|---|---|---|---|---|---|---|---|---|---|
| native | 5 | 0 | 0.00 [0.00, 0.43] | 0.929 | 0.014 | 3.0 | 0.0 | 106220 | 0.0 |
| native+ponder | 5 | 2 | 0.40 [0.12, 0.77] | 0.891 | 0.039 | 1.2 | 23.8 | 146353 | 0.0 |

Per-seed winners (paired): native, native+ponder
| seed | native | native+ponder |
|---|---|---|
| 0 | expert | expert |
| 1 | expert | **LLM** |
| 2 | expert | heuristic |
| 3 | heuristic | **LLM** |
| 4 | expert | heuristic |

Full table — native:
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:expert | 5 | 4 | 0.8 [0.376, 0.964] | 0.2 | 21.5 | 6.8 | 0 | 1067 |
| baseline:heuristic | 5 | 1 | 0.2 [0.036, 0.624] | 0.0 | 25 | 7.0 | 0 | 985 |
| llm:nvidia/nemotron-3-super-120b-a12b:free:bayesian_probabilist:native:compact | 5 | 0 | 0.0 [0.0, 0.434] | 0.0 | None | 7.0 | 0 | 948 |

Full table — native+ponder:
| agent | games | wins | win_rate | false_accusation_rate | avg_turns_to_win | avg_suggestions_per_game | illegal_attempts | elo |
|---|---|---|---|---|---|---|---|---|
| baseline:heuristic | 5 | 2 | 0.4 [0.118, 0.769] | 0.0 | 16.5 | 6.2 | 0 | 1015 |
| llm:nvidia/nemotron-3-super-120b-a12b:free:bayesian_probabilist:native:compact | 5 | 2 | 0.4 [0.118, 0.769] | 0.0 | 22.5 | 6.2 | 0 | 1010 |
| baseline:expert | 5 | 1 | 0.2 [0.036, 0.624] | 0.0 | 19 | 5.8 | 0 | 974 |

Cost: `{'calls': 805, 'cached_calls': 169, 'prompt_tokens': 1857694, 'completion_tokens': 455075, 'usd': 0.0, 'max_usd': 0.1}`
# Symbolic deduction tools

> Playing at a real table? `clue analyze` and the web **Analyst** page expose these tools (plus
> coach-style guidance) for hand-entered observations — see [analyst.md](analyst.md).

Location: `clue/tools/deduction.py`. The functions reason from a viewer's `Notebook`, player list,
hand sizes, and edition; they do not inspect hidden game state. They are used in three ways:

1. Precomputed in the LLM prompt as `analysis` when tools are enabled (the default).
2. Called by `LLMPlayerAgent._tool`; `TOOL_SPECS` provides schemas for supported native function-calling APIs.
3. Used by baseline agents, including the heuristic and expert bots.

Tool calls made through an active game manager are recorded privately in the replay for the calling player.

| Tool | Signature | Returns |
|---|---|---|
| `get_unseen_cards` | `(nb, edition)` | Suspects, weapons, and rooms not in your hand, face-up, or shown to you |
| `get_possible_solutions` | `(nb, players, hand_sizes, edition)` | Exact path: exhaustive feasible triples. Sampled path: potential triples surviving propagation, which may include unverified candidates |
| `solution_probabilities` | `(nb, players, hand_sizes, edition)` | `{n_possible, combos (top 10), cards (marginals), best, best_prob, exact}`; on sampled Large results, `n_possible` counts candidates surviving propagation, not verified assignments |
| `holder_probabilities` | `(nb, players, hand_sizes, edition)` | `card -> {player or envelope: probability}`; exact when counted exhaustively, estimated when sampled |
| `hard_deductions` | `(nb, players, hand_sizes, edition)` | Sound forced facts beyond the notebook, e.g. `"P3 must hold Lounge"` or `"SOLVED: …"` |
| `opponent_threat` | `(nb, players, me, hand_sizes, edition, history, eliminated)` | Per-rival candidate/threat estimates, plus `max_threat`, `most_dangerous`, and `p_any_wins_before_my_turn` |
| `suggestion_ev` | `(nb, players, me, suspect, weapon, room, edition)` | Heuristic novelty/disprover score and related details |
| `can_accuse_confidently` | `(nb, players, threshold, hand_sizes, edition)` | Best combo and confidence vs. threshold, plus `exact` to identify exhaustive counting vs. sampling |
| `update_notebook` | `(nb, note)` | Appends a note to the caller's private notebook |
| `best_suggestion` | `(nb, players, me, room, edition, rng)` | Highest-`suggestion_ev` suspect/weapon pair, with a seeded tie-break |

## Inference and solver limits

`solve(nb, players, hand_sizes, edition) -> Solution` counts full card assignments consistent with known
holders, `not_held`, `has_one_of` constraints, and exact hand sizes. Unconstrained cards are counted
combinatorially rather than branched on individually. The exact dynamic-programming path is used only when
there are at most 6 players, at most 22 constrained cards in the solver's head set, and at most 21 cards in
the edition's deck. These are implementation bounds, not user-configurable guarantees. The 36-card Large
edition always uses constraint propagation plus deterministic sampling (`SAMPLES = 400`, with a node budget);
`Solution.exact` is false for that path. Large-edition candidate lists and posterior probabilities are
therefore estimates, not exhaustive results.

The sampled path's propagation establishes only sound forced facts; `hard_deductions` does not promote
sampling frequency into certainty. In exact cases, `combos` stores counts of complete assignments per
solution triple, and the solver derives exact envelope and holder marginals. In sampled cases, candidate
triples are retained when propagation has not ruled them out, and sample counts are smoothed over that set;
thus the candidate list can include triples not verified by a complete deal, while the posterior frequencies
remain estimates. `solution_probabilities` returns `exact: true` or `false` from the underlying result
(including the no-candidate case). Treat a singleton sampled candidate list as uncertain.

Hard deductions are not auto-written into a human's notebook; the TUI's coach mode is gated, while bots and
LLMs can use the facts in their analysis.

## Opponent model (`clue/tools/opponent.py`)

For each rival, the model constructs a shadow notebook from public history and information available to the
viewer. It estimates a rival's remaining candidate count and chance to win before the viewer's next turn. The
estimate uses the same edition-aware solver, so Large-edition threat values inherit its sampling limits. The
reported correlation (0.97) is a historical calibration result on the project's Classic test games, not a
formal guarantee. The expert bot uses the estimate in its gamble decision; LLMs receive it as
`analysis.opponent_threat`.

## Suggestion value (`suggestion_ev`)

The score is `0.5 * novelty + 0.3 * (possible_disprovers / max(1, players - 1)) + 0.2 * (1 - own_cards / 3)`.
Novelty is the fraction of the three cards not already known outside the envelope; possible disprovers are
opponents not known to lack all three. This is a fast heuristic, not entropy or an exact expected information
gain calculation.

## Guarantees and limits

- Tools use only the viewer's notebook and public observation context; they cannot peek at hidden hands or the solution.
- They do not mutate game state. `update_notebook` changes only the caller's notebook notes.
- Exactness is exposed by `Solution.exact` and `solution_probabilities.exact`. Strategies should treat confidence
  as an estimate whenever `exact` is false; `n_possible == 1` in a sampled candidate list alone does not prove
  that only one solution exists.

## Ablation

`tools: false` (or `--no-tools`) skips the precomputed analysis bundle and recommendation; the model receives
the raw observation. Native tool mode still has the precomputed analysis as a floor when tools are enabled.
The offline ablation figures in `eval/report.md` are a historical benchmark snapshot; rerun `python -m clue eval`
to regenerate results for the current code.

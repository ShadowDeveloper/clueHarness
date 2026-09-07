# Symbolic deduction tools

Location: `clue/tools/deduction.py`. Pure functions over a `Notebook` (+ player list and hand sizes).
They are used three ways:
1. **Pre-computed** into the LLM prompt as `analysis` (default, `tools: true`).
2. **Callable** by `LLMPlayerAgent._tool(name, **args)` — the `TOOL_SPECS` list is an OpenAI-style
   function schema if you wire native function calling (see `extending.md`).
3. By `BaselineHeuristicBot`, so the heuristic bot and the LLM's `recommended_action` share one brain.

Every invocation is written to the replay as a `tool_call` record (private to the caller).

| Tool | Signature | Returns |
|---|---|---|
| `get_unseen_cards` | `(nb, edition)` | `{suspects, weapons, rooms}` not in hand / face-up / shown to you |
| `get_possible_solutions` | `(nb, players, hand_sizes, edition)` | list of `(suspect, weapon, room)` consistent with all constraints |
| `solution_probabilities` | `(nb, players, hand_sizes, edition)` | exact `{n_possible, combos (top-10), cards (marginals), best, best_prob, exact}` |
| `holder_probabilities` | `(nb, players, hand_sizes, edition)` | exact `card -> {player or envelope: probability}` |
| `hard_deductions` | `(nb, players, hand_sizes, edition)` | forced facts beyond the notebook, e.g. `"P3 must hold Lounge"`, `"SOLVED: …"` |
| `opponent_threat` | `(nb, players, me, hand_sizes, edition, history, eliminated)` | per rival `{n_possible, p_win_next_turn, unrefuted, repeat_suggestion, known_cards}` + `max_threat`, `most_dangerous`, `p_any_wins_before_my_turn` |
| `suggestion_ev` | `(nb, players, me, suspect, weapon, room, edition)` | `{novelty, possible_disprovers, first_unknown_disprover, own_cards_included, score}` |
| `can_accuse_confidently` | `(nb, players, threshold, hand_sizes, edition)` | `{accuse, best, confidence, n_possible, threshold}` |
| `update_notebook` | `(nb, note)` | appends to `nb.notes` |
| `best_suggestion` | `(nb, players, me, room, edition, rng)` | argmax of `suggestion_ev` over (suspect, weapon) with seeded tie-break |

## Algorithms

### Exact solver (`clue/tools/solver.py`)
`solve(nb, players, hand_sizes, edition) -> Solution` enumerates every candidate envelope triple and, for
each, **counts the number of complete hand assignments** consistent with the notebook: known holders,
`not_held`, every `has_one_of` triple, exact hand sizes. Cards not mentioned by any constraint are handled
combinatorially (multinomial over remaining capacity) so the search only branches over constrained cards;
`_count_assignments` is memoised. Output: `combos` (triple → count), exact `card_probs` (P(card in envelope)),
exact `holder_probs` (card → {player|envelope: p}) and `certain_holder` (forced facts). Verified against a
brute-force enumerator; typical call < 20 ms, worst observed 0.3 s in 5-player games.

`get_possible_solutions`, `solution_probabilities` (`exact: True`), `can_accuse_confidently`,
`holder_probabilities` and `hard_deductions` are all thin wrappers over `solve()`. **Hard deductions are
never auto-written into a human player's notebook** — they are shown only in coach mode / analysis payloads
for bots and LLMs, so humans still get to deduce for themselves.

### Opponent modelling (`clue/tools/opponent.py`)
For each rival we build a **shadow notebook** from the public history plus everything we personally showed
them, seed it with the cards our own posterior places in their hand with certainty, and fill each disproof
they received from a third party with the card the shower most probably holds (from our posterior). Running
`solve()` on the shadow gives an estimate of the rival's candidate count, discounted by 0.75 per card of
their hand we could not place. Calibration over full games: correlation 0.97 with the rival's true solver
count; every rival that was actually solved was estimated at ≤ 3 candidates. ~40 ms per call. Used by
`BaselineExpertBot` for its decision-theoretic gamble rule and injected as `analysis.opponent_threat` for LLMs.

### Information value (`suggestion_ev`)
`score = 0.5·novelty + 0.3·(possible_disprovers / (n−1)) + 0.2·(1 − own_cards/3)` where *novelty* is the
fraction of the three cards still unknown to you and *possible_disprovers* counts opponents who are not
proven to lack all three. Heuristic, not an exact entropy computation — chosen for speed (it is evaluated 36
times per suggestion opportunity).

## Guarantees and limits
* Tools only ever read the viewer's notebook; they cannot peek at hidden state (they don't receive it).
* They never mutate game state; `update_notebook` mutates only the caller's own notebook.
* Approximate posterior ⇒ a strategy asking for "≥ 90 % confidence" gets a Monte-Carlo estimate; with
  `n_possible == 1` the estimate is exactly 1.0.

## Ablation
`tools: false` (or `--no-tools`) skips the bundle and the recommendation entirely; the model receives the
raw observation only. Offline result (50 games, `eval/report.md`): win-rate 0.30 → 0.04 and
false-accusation rate 0.00 → 0.86 without tools.

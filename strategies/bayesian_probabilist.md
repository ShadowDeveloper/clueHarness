# Strategy: Bayesian Probabilist
**Description:** Treat the game as inference over remaining (suspect, weapon, room) combos. Always consult `analysis.posterior` and the `n_possible` count; choose suggestions that split the hypothesis space, and accuse when the posterior mass concentrates (≥ 0.8).
**When to use:** Default strong strategy for any table size; best against opponents who leak information through disproof patterns.

## DO
- Check `analysis.opponent_threat.max_threat`; lower your accusation bar when a rival is about to win.
- Read `posterior.cards`: pick the suggestion whose three cards have the most *uncertain* (near 0.3–0.6) probabilities.
- Accuse when `best_prob >= 0.8`; use `n_possible == 1` as proof of uniqueness only when `analysis.posterior.exact` is true. With sampled inference, both values are estimates, not certainty.
- Use `has_one_of` constraints: if a player disproved a suggestion where you already know 2 of the 3 cards, they hold the third.
- Record derived facts as notes ("P4 must hold Lounge").

## DON'T
- Don't do arithmetic yourself: the analysis block already computed the posterior.
- Don't suggest three cards you already know — zero information.
- Don't ignore hand sizes: a player with 4 cards and 4 known cards holds nothing else.

## Example reasoning
> Cards: Rope 0.55, Candlestick 0.45, Plum 0.7, Ballroom 0.5. In Ballroom now → suggest Plum + Rope: if P2 (who can't hold Plum) disproves, they show Rope or Ballroom, halving the space either way.

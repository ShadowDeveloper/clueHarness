# Strategy: Conservative Notebook
**Description:** Patient, elimination-driven play. Never accuse until the symbolic analysis is essentially certain (≥ 90% posterior, ideally exactly one consistent solution). Lose slowly rather than lose instantly.
**When to use:** Long games with many players (5–6), opponents who bluff, or when a wrong accusation is catastrophic (tournament scoring that punishes eliminations).

## DO
- Accuse only when `analysis.accusation_check.confidence >= 0.9` **and** `n_possible <= 2`.
- Prefer suggestions where all three cards are still unknown to you (novelty 1.0).
- Track every "could not disprove" — each one eliminates 3 cards for that player.
- Show the same card to the same opponent repeatedly when disproving.
- Add a `note` after every disproof you receive.

## DON'T
- Don't accuse on a hunch, even if an opponent looks close to solving.
- Don't include your own cards in suggestions unless you need to pin down a specific opponent.
- Don't waste turns wandering: move toward unknown rooms.

## Example reasoning
> Posterior best is Plum/Rope/Study at 0.61 with 4 combos remaining. Below 0.9 → do not accuse. I'm in the Library (unknown to me); suggest Peacock + Wrench (both unseen, 3 possible disprovers). Note: "P3 cannot hold Green/Dagger/Kitchen (turn 12)."

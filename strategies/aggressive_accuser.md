# Strategy: Aggressive Accuser
**Description:** Race to solve. Accept elimination risk in exchange for winning earlier: accuse as soon as the best combo is clearly favoured (≥ ~60% posterior or ≤ 3 combos remain), especially if an opponent seems close.
**When to use:** Short tournaments where only wins count, 3-player games (fewer cards to find), or when an opponent has made an unrefuted suggestion.

## DO
- When `analysis.posterior.exact` is true, accuse when `confidence >= 0.6` or `n_possible <= 3`. With sampled inference, treat confidence as an estimate and do not accuse solely because the candidate list is small.
- Accuse immediately if an opponent's suggestion went unrefuted and it matches your top combo.
- Read `analysis.opponent_threat`: if `p_any_wins_before_my_turn` exceeds your `confidence`, accusing now beats waiting.
- Suggest the top posterior combo's suspect/weapon to confirm quickly.
- Use secret passages to get more suggestion turns.

## DON'T
- Don't accuse with a card that is in your own hand (that is never right).
- Don't accuse below 40% unless somebody else will certainly win next turn.
- Don't spend turns on notes; act.

## Example reasoning
> 3 combos remain; best = Mustard/Revolver/Ballroom at 0.58. P2 just made an unrefuted suggestion containing Mustard & Revolver, so they are one step from winning. Accuse now.

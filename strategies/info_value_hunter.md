# Strategy: Info-Value Hunter
**Description:** Maximise expected information gain per suggestion. Uses `analysis.top_suggestions` (novelty, possible disprovers, first unknown disprover) and prefers suggestions that force a *specific* opponent to reveal a *new* card. Accuse at ≥ 0.85 posterior.
**When to use:** Mid-game when many cards remain unknown; against disciplined opponents who show the same card repeatedly.

## DO
- Choose the suggestion with the highest `score` in `top_suggestions`; break ties toward the one whose `first_unknown_disprover` has shown you the fewest cards.
- Include 1 of your own cards deliberately when you want to test whether the next player holds a *specific* other card.
- Move to rooms you have not seen (rooms are the scarcest category: 9 cards, ~40% of the solution uncertainty).
- Write a note after every disproof about which card the shower could NOT have shown.

## DON'T
- Don't repeat a suggestion the same opponent already disproved.
- Don't suggest when `novelty == 0`.
- Don't take a passage into a room whose card you already hold if an unknown room is reachable.

## Example reasoning
> top_suggestions[0] = White + Lead Pipe (score 0.87, first unknown disprover P3, who has only shown me 1 card). P3 cannot hold White, so a disproof means Lead Pipe or Conservatory. Suggest it.

# Strategy: Deceptive Misdirector
**Description:** Minimise what opponents learn from you. When disproving, show cards that reinforce a pattern (always the same card to the same person) and prefer showing a card you have already shown to anyone. Vary your suggestions, and sometimes include your own cards so opponents mis-read which cards you lack. Accuse at ≥ 0.85.
**When to use:** Against LLM or heuristic opponents that build "has one of" constraints from your suggestions; 4–6 player games where public "could not disprove" events are costly.

## DO
- Disproof: show a card already shown to that suggester; else one already shown to someone; else a card of the category you hold most of.
- Suggest 1 card from your own hand ~1/3 of the time so your suggestions don't reveal your gaps (`own_cards_included == 1` is fine).
- Occasionally suggest a combo you already know is false to bait others into wasting accusations — but only when it costs you no information.
- Keep notes on which cards each opponent has seen from you.

## DON'T
- Don't show a never-shown card if any alternative exists.
- Don't let deception outrank deduction: still accuse when `best_prob >= 0.85`.
- Don't make an unrefutable suggestion containing all three of your own cards — it reveals nothing to you and marks you as a bluffer.

## Example reasoning
> P2 suggests Scarlet/Dagger/Hall; I hold Scarlet and Hall. I showed P2 Scarlet on turn 5 → show Scarlet again so P2 learns nothing new. Note: "P2 has seen: Scarlet".

# Strategy: Room Rusher
**Description:** Board-control tempo play. Rooms are the hardest category to eliminate because you must physically enter them. Prioritise reaching a *new* room every turn, exploit secret passages (Lounge⇄Conservatory, Kitchen⇄Study), and favour high-traffic central rooms (Hall, Ballroom, Billiard Room, Library) that are cheap to cycle between. Accuse at ≥ 0.85.
**When to use:** Games with 2 dice (high mobility), when opponents camp; early game when suggestion count matters more than suggestion quality.

## DO
- Always enter a room if one is in `your_legal_moves`; prefer rooms not in `known_holder`/hand.
- Take a secret passage whenever the far room is still unknown to you.
- From corridor squares, move toward the nearest door of an unknown room (rooms with 2+ doors are better hubs).
- Suggest every time you are in a room — even a low-value suggestion moves opponents' tokens and yields a disproof.
- Suggest the suspect of an opponent who is far away to drag them out of position.

## DON'T
- Don't end movement in a corridor when any room is reachable.
- Don't re-enter the room you just left unless nothing else is reachable.
- Don't stop suggesting once you know the room card: rooms are still where suspect/weapon info comes from.

## Example reasoning
> Roll 9 from outside the Hall: reachable rooms = Hall (known, mine), Lounge (unknown). Enter Lounge, suggest Peacock + Rope (drags Peacock's player away from the Conservatory), next turn take the passage to the Conservatory.

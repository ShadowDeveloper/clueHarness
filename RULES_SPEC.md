# RULES_SPEC.md — Locked Rules for the Clue AI Harness

**Source edition:** Hasbro / Parker Brothers *CLUE Classic Detective Game* instructions
(https://www.hasbro.com/common/instruct/clueins.pdf — the 2002 US edition, which uses **two dice**).
Where the 1996 one-die edition differs, it is available via config. This specification documents the Classic
baseline; Modern substitutes Dr. Orchid for Mrs. White, while the Large edition uses a 36-card set, 3–12 seats,
and its own board geometry and passage pairs. The core turn and deduction rules are shared. Edition-specific
cards, limits, boards, and the solver's sampling behavior are documented in `README.md`, `docs/configuration.md`,
and `docs/tools.md`. Every Classic baseline edge-case decision is enforced in `clue/rules/`.

## 1. Components
| Category | Cards |
|---|---|
| Suspects (6) | Miss Scarlet, Col. Mustard, Mrs. White, Mr. Green, Mrs. Peacock, Prof. Plum |
| Weapons (6) | Candlestick, Dagger, Lead Pipe, Revolver, Rope, Wrench |
| Rooms (9) | Hall, Lounge, Dining Room, Kitchen, Ballroom, Conservatory, Billiard Room, Library, Study |

`edition: modern` renames **Mrs. White → Dr. Orchid** (2016+). Default `classic`.

## 2. Setup
- One suspect, one weapon, one room go in the envelope (chosen by the seeded RNG).
- Remaining 18 cards are shuffled together and dealt clockwise starting with the first player.
- **Uneven deal (4 or 5 players)** — configurable (`deal_remainder`):
  - `uneven` (**default**, official): "some players may have more cards than others."
  - `faceup` (house variant): the 18 mod N leftover cards are placed face-up and are public knowledge to everyone.
- Seats are assigned to suspect tokens in canonical order (Scarlet, Mustard, White, Green, Peacock, Plum). Unused suspect tokens still sit on their start squares (they can be summoned by suggestions).
- Weapons tokens have no rule effect; we track them in rooms cosmetically.
- **Miss Scarlet moves first** (official). Play proceeds clockwise (seat order).

## 3. Board (Hybrid model — user decision)
Movement uses a **hybrid** board: a real 24×25 corridor grid transcribed from the classic board layout with
exact doors, start squares and the four secret passages, but **rooms are single nodes** (no interior squares).
- Corridor movement: orthogonal steps, no diagonal, cannot enter the same square twice in one turn, cannot
  enter a square occupied by another token (blocking).
- A door is an edge between a corridor square and a room node. Passing through the door costs 1 step
  (moving from the corridor square in front of the door into the room). Entering a room **ends movement**
  even if pips remain.
- **Door blocking**: because rooms are nodes, we implement the rulebook's "you may not pass through a door
  blocked by an opponent" as: a room can always be entered (rooms hold unlimited tokens), but the corridor
  square outside a door can be occupied and thus block the approach. This is a documented simplification.
- Leaving a room: choose any door of that room; the first step is onto that door's corridor square (must be
  unoccupied), and you may not re-enter the same room in the same turn.
- Secret passages: Lounge⇄Conservatory, Kitchen⇄Study. Taking a passage replaces the dice roll and ends
  movement (you may then suggest).
- Dice: **2d6 default** (`dice: 2`); `dice: 1` for the 1996 edition.
- You may not forfeit a turn to stay in a room: if a legal move exists you must move (or use a passage or
  accuse). If you are boxed in (no legal moves) you stay and may not suggest unless you were moved in by a
  suggestion since your last turn.

## 4. Turn structure
1. **Move phase**: `roll` (then choose a destination among reachable squares/rooms), or `passage`, or
   `accuse` directly (accusations are allowed at any point in your turn from anywhere on the board).
2. **Suggest phase** (only if you ended movement in a room, or were pulled into a room by a suggestion since
   your last turn and chose not to move — "you may make a suggestion immediately in the room you were moved
   to"): suggest the *current room* + any suspect + any weapon. The named suspect token (and weapon) moves
   into that room. A suggestion is optional.
3. **Disproof**: going clockwise from the suggester, the first player holding ≥1 of the three cards must
   show exactly one such card **privately** to the suggester. If they hold several they choose. Eliminated
   players still disprove. Players who cannot disprove publicly say so. If nobody can, that is public.
4. **Accuse phase (optional)**: name any suspect/weapon/room. Correct → win. Wrong → the player is
   eliminated: they no longer roll, move, suggest, or accuse, but they still disprove and their token
   remains on the board (and can be moved by suggestions).
5. `end_turn`.

## 5. Repeat-room rule
Official: "You may not re-enter the same room on a single turn. If you wish to make a suggestion in the same
room next turn you must either leave and re-enter..." — Implemented as: a player may suggest only if
they **entered** the room this turn (by move, passage, or having been moved there by another player's
suggestion since their last turn). Staying still yields no suggestion.

## 6. End of game
- A correct accusation wins immediately.
- If all players are eliminated, the game ends with no winner (`winner = null`), solution revealed.
- Safety cap: `max_turns` (default 400 player-turns) ends the game as a draw — prevents infinite loops in
  bot tournaments.

## 7. Information & privacy
- Shown cards are visible only to suggester and shower. Everyone else sees "P3 disproved P1's suggestion".
- Hands, the envelope, and shown cards never appear in another player's observation or redacted replay.

## 8. Public-notebook facts automatically derived (no LLM)
- `X could not disprove (S,W,R)` → X holds none of S,W,R.
- `X disproved (S,W,R)` → X holds at least one of S,W,R.
- Shown card → suggester knows X holds that card.
- A suggestion nobody disproved: all three cards are in the envelope or the suggester's own hand.

## 9. Optional house rules (all default off)

Documented in `docs/variants.md`; none of them alters sections 1–8 unless switched on in `GameConfig`:
`teams` (shared hands, teammates skipped in the disproof round, team win), `private_disproofs` (only the parties
involved learn who passed / who showed; bystanders see "someone showed a card"), `wrong_accusation: skip_turns`
(sit out `accusation_penalty_turns` turns instead of elimination), `shuffle_seats` (seeded random seating).

# The analyst: probabilities + coaching for a real-table game

`clue analyze` (TUI/CLI), the web UI's **Analyst** page, and `POST /api/analyze` expose the harness's
analytical tools (the exact-or-sampled solver, hard deductions, opponent threat, suggestion EV) and
coach-style guidance for a game you are playing **away from the computer**: type in your cards and every
suggestion you observe, and the engine tells you what is provable, what is probable, and what to do next.

A static build of the web Analyst is deployed on **GitHub Pages**:
<https://shadowdeveloper.github.io/clueHarness/> — it runs entirely in the browser (no backend; nothing
you type leaves the page).

## What you enter

* edition (`classic` / `modern` / `large`), the seating order, and which seat is you;
* the cards in your hand, plus any face-up cards dealt to nobody;
* optional explicit `hand_sizes` (defaults to an even deal, with your seat pinned to the number of cards
  you entered — enter them explicitly for uneven house deals);
* optional `card_names` display renames — canonical card → the name printed on *your* copy of the game
  (localisations, house variants, "Rev. Green" vs "Mr. Green", …). Renames are purely cosmetic: the solver
  and the session JSON always store canonical names, but every surface (TUI, CLI report, web page, guide
  and deduction sentences) renders through the mapping. Validation rejects unknown cards, empty labels,
  two cards sharing a label, and a label that still belongs to a different card;
* a list of **observations**:
  * **suggestion** — who suggested which suspect/weapon/room, who disproved it (or nobody), and, when you
    were the suggester or the disprover, which card was shown. Players seated between the suggester and
    the disprover are automatically marked as holding none of the three; an undisproved suggestion marks
    everyone but the suggester;
  * **fact** — "player X holds / lacks card Y" for anything else you know (e.g. a card you were shown in
    a previous session, a glimpsed card, a houserule reveal).

The session is converted into the exact event stream the engine would have produced in a hosted game and
replayed through the standard per-player `Notebook`, so the tools reason from the same evidence model as
live games (`clue/tools/analyst.py`).

## What you get back

* **solution posterior** — surviving (suspect, weapon, room) candidates with exact probabilities
  (assignment counting) on Classic/Modern tables, deterministic-sampling estimates on Large
  (`exact: false`);
* **holder probabilities** — P(card is in the envelope / held by each player) for every card;
* **hard deductions** — provable facts beyond your notebook ("Bob must hold Lounge", "Revolver is in the
  envelope", "SOLVED: …");
* **opponent threat** — how close each rival looks to solving (shadow-notebook model);
* **guide** — coach-style advice: most likely envelope, whether accusing is justified against a
  confidence threshold (default 0.9, `--threshold`), the highest-information suggestion to make next, and
  contradiction diagnostics when your entries cannot all be true.

## TUI

```bash
clue analyze                      # setup wizard, then the live analyst screen
clue analyze mygame.json          # resume a saved session (autosaved back to the same file)
```

Keys: `s` add a suggestion, `f` add a fact, `u` undo the last observation, `n` rename a card (how it is
printed on your copy; empty restores the standard name), `e` edit the setup, `ctrl+s` save the session
JSON, `q` quit. Every change re-runs the solver and refreshes the probability grid, candidate list, and
guide.

## Plain CLI / scripting

```bash
clue analyze mygame.json --ui cli              # one-shot rich report in the terminal
clue analyze mygame.json --ui cli --out r.json # also dump the full JSON report
```

Session JSON shape (also what the TUI saves and the web page imports/exports):

```json
{
  "edition": "classic",
  "players": ["Me", "Alice", "Bob", "Cara"],
  "me": "Me",
  "my_cards": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
  "faceup": [],
  "hand_sizes": null,
  "card_names": {"Lead Pipe": "Pipe", "Mrs. White": "Dr. Orchid"},
  "observations": [
    {"type": "suggestion", "suggester": "Me", "suspect": "Prof. Plum", "weapon": "Dagger",
     "room": "Lounge", "disprover": "Bob", "shown_card": "Dagger"},
    {"type": "suggestion", "suggester": "Alice", "suspect": "Mrs. Peacock", "weapon": "Revolver",
     "room": "Kitchen", "disprover": "Cara"},
    {"type": "suggestion", "suggester": "Bob", "suspect": "Col. Mustard", "weapon": "Lead Pipe",
     "room": "Ballroom", "disprover": null},
    {"type": "fact", "player": "Alice", "card": "Library", "has": true}
  ]
}
```

## Web UI and GitHub Pages

The **Analyst** page (`/analyze`) is part of the SPA served by `clue web`. The math runs client-side in
TypeScript (`web/src/analysis/`), a direct port of `clue/tools/{solver,deduction,opponent,analyst}.py`
cross-validated against Python-generated fixtures (`npm test`; regenerate with
`python web/scripts/make_fixtures.py` after touching the Python solver). Because no backend is needed,
the same page is deployed standalone to GitHub Pages by `.github/workflows/pages.yml`
(`npm run build:pages` → `web/dist`). Sessions autosave to `localStorage` and can be exported/imported
as the JSON above — the same files work in the TUI.

`POST /api/analyze` (body = session JSON, optional `?threshold=`) returns the authoritative Python
report for API users; `GET /api/docs` has the schema. Structured report fields (combos, holders,
marginals) stay canonical; the report's `card_names` echo lets clients label them, and the
human-readable `deductions`/`advice` strings arrive already labelled.

The page is **mobile-friendly** (it is the surface you would use at a real table): single-column layout,
larger touch targets, and a probability grid tuned to fit a phone screen. When the grid is still wider
than the screen (Large edition, many players) it scrolls sideways inside its own pane with a visible
scrollbar, edge shadows, a "swipe" hint, and sticky card column + player header, so nothing is hidden
silently. Face-up cards need no keyboard: with the *face-up cards* toggle on, tapping a card cycles
*in my hand -> face-up -> unmarked* (desktop shift-click still jumps straight to face-up). The
**Rename cards** editor in the setup panel adapts the card names to your copy of the game.

## Guarantees and limits

Same as the underlying tools (see [tools.md](tools.md)): the analyst reasons only from what you typed,
probabilities assume consistent deals are equally likely and exact hand sizes, Large-edition results are
sampled estimates (`exact: false`), and hard deductions are sound on both paths. Direct contradictions
(e.g. a fact that conflicts with an observed pass) are detected and reported instead of silently
producing nonsense. The in-game coach (`h` in the play TUI) additionally suggests a concrete legal move,
which needs a live game and is not part of the standalone analyst.

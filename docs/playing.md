# Playing

## Interfaces
| Mode | Command | When |
|---|---|---|
| **TUI** (default with a human) | `python -m clue play --players human,llm:bayesian,llm:aggressive,baseline` | Interactive play; full-screen board, notebook, log, action menu |
| **Spectate** in the TUI | `python -m clue play --players llm:bayesian,baseline,baseline --spectate` | Watch AIs play; pause / change speed |
| Plain CLI | `... --ui cli` | Dumb terminals, piping, transcripts (see `demo_game.md`) |
| Headless | `python -m clue play --players baseline,baseline,baseline --quiet` | Scripting / CI |

The TUI is built on [Textual](https://textual.textualize.io/). It runs in any modern terminal
(≥ 120×36 recommended), supports mouse and keyboard, and never touches game logic: the human seat is an
ordinary `PlayerAgent` (`clue/tui/app.py: TUIHumanAgent`) whose decisions are posted from the UI thread to
the game loop thread through a queue.

## The screen
```
╭─ Board ───────────────╮╭─ Notebook ✔ has ✘ hasn't ? unknown ─╮╭─ What happened ──────────╮
│   KITCHEN  BALLROOM   ││ Card         P1 P2 P3 P4            ││ ━━━ YOUR TURN ━━━        │
│    G  · ▢  S W P  ▢   ││ Rope         ✘  ?  ✘  ?             ││ P1 rolled [2,6] = 8      │
│ ▢ door ⇄ passage      ││ Wrench       ✔  ·  ·  ·  yours      ││ P3 suggests …            │
│ ◆ reachable ░ cellar  ││ Study        ?  ?  ✘  ✘             ││   P1 showed the Wrench…  │
│ S Miss Scarlet ← you  │╰─────────────────────────────────────╯╰──────────────────────────╯
│ M Col. Mustard …      │╭─ Deductions ────────────────────────╮┏━ Your move ━━━━━━━━━━━━━━┓
╰───────────────────────╯│ • P4 holds at least one of …        │┃ It's your turn.          ┃
                         ╰─────────────────────────────────────╯┃ • Roll the dice and move ┃
                                                                ┃ [Roll (r)] [Accuse (a)]  ┃
 You are Miss Scarlet (P1) in the Ballroom · your cards: … · turn 24                       ┛
 r Roll  p Passage  s Suggest  a Accuse  e End turn  esc Back  space Pause  + -  q Quit
```
`docs/tui_screenshot.txt` is a real capture.

### Board
Rooms are shaded blocks with their names; `·` corridor squares; `▢` the square outside a door; `⇄` in a
corner room marks a secret passage; `░` the cellar. Tokens are monochrome symbols on the suspect's colour: ♛ Scarlet (red), ★ Mustard (yellow),
✚ White / Dr. Orchid (white), ♣ Green (green), ❋ Peacock (blue), ✎ Plum (magenta) — with a legend
underneath (yours is marked `← you`). Use `--no-emoji` to fall back to letters S/M/W/G/K/P if your terminal
font lacks emoji. Small
lower-case letters inside rooms are weapon tokens. After you roll, every square or room you can reach is
highlighted with `◆` / a highlighted room name.

### Notebook
One row per card, one column per player, derived mechanically from what you are entitled to know:

| Symbol | Meaning |
|---|---|
| `✔` | that player holds the card (your own hand, or shown to you) |
| `✘` | that player provably does **not** hold it (failed to disprove, or an unrefuted suggestion) |
| `·` | not relevant — someone else has it |
| `?` | unknown |
| `yours` / `P3 has it` / `face-up` / **`ENVELOPE!`** | status; `ENVELOPE!` appears when every opponent is `✘` |

### Deductions
"P4 holds at least one of …" facts (someone disproved but not to you), unrefuted suggestions, and LLM notes
when spectating an LLM seat.

### What happened
The public history as *you* may see it: shown cards appear (green) only when you were the suggester or the
shower; otherwise "P2 showed a card to P4". Your own turns are marked `━━━ YOUR TURN ━━━`.

### Your move (action panel)
The panel is **guided**: it tells you what you can do right now and shows only the relevant buttons.

| Situation | Panel |
|---|---|
| Start of turn | banner "It's your turn." · buttons **Roll (r)** / **Passage (p)** (corner rooms) / **Accuse (a)**; if you were dragged into a room, also **Suggest (s)** |
| After rolling | "You rolled 8. Where do you want to go?" — a list of rooms first ("Enter the Hall — you can suggest there") then corridor squares, mirrored by `◆` on the board. Enter / **Confirm** |
| In a room | **Suggest (s)** / **Accuse (a)** / **End turn (e)** |
| Suggest / Accuse | step-by-step picker: *suspect → weapon (→ room)*; chosen items shown in the banner ("Step 2 of 3"); cards tagged `(your card)` or `(seen — not in envelope)`; **Back / Esc** undoes one step |
| Someone's suggestion you must disprove | "P2 suggested … choose which card to show P2" with only the cards you may show (skipped automatically when you have exactly one) |
| Game over | winner and solution in the banner; `q` quits |

Everything is clickable; every button has the hotkey in its label. A terminal bell rings whenever it is
your decision.

### Hotkeys
`r` roll · `p` passage · `s` suggest · `a` accuse · `e` end turn · `Esc` back · `space` pause (spectate) ·
`+`/`-` AI pacing · `ctrl+s` save · `h` coach · `v` cycle spectator view · `q` quit (saves first if the game is still running).

## Turn walk-through
1. `roll` (or `passage` when in a corner room, or accuse right away).
2. Choose a destination among the exact-distance corridor squares and any reachable rooms. Entering a room
   ends movement.
3. If you entered a room: `suggest …`, or `end_turn`. Suggesting moves the named suspect token (and weapon)
   into your room; the first clockwise player who can disprove does so privately.
4. Optionally `ACCUSE …` — from anywhere, any time on your own turn. Wrong = eliminated (you still disprove).
5. `end_turn`.

If you were dragged into a room by someone's suggestion, on your next turn you may `suggest …` there
immediately without rolling (the menu offers both).

## After the game
The winner and solution are shown in the action panel; press `q`. Replays are written to
`replays/game_<seed>.jsonl` (unredacted) and `replays/game_<seed>_redacted_<Pn>.json` (one per player).
Inspect with `python -m clue replay replays/game_<seed>.jsonl`.

## Saving and resuming
A game in progress can be stopped at any point and continued later - with **every player's private memory
intact**, so the resumed game is exactly the game you left (same dice, same bot decisions; the replay hash of
a resumed game equals that of an uninterrupted one).

* **TUI:** the game is checkpointed automatically after every action to `saves/game_<seed>.json`
  (`--save PATH` to choose the file, `--no-autosave` to turn it off). `ctrl+s` saves on demand; `q` while the
  game is still running saves, stops the bots at the next safe point and exits, printing the resume command.
* **Plain CLI / automation:** add `--save PATH` (checkpoint rewritten atomically after every action, so a crash
  or Ctrl-C loses nothing).
* **Resume:** `clue play --resume saves/game_<seed>.json` (add `--ui cli` / `--tui`, `--delay`, `--ponder`,
  `--provider` as usual - the players, seed and rules come from the file). The checkpoint keeps being updated
  and is deleted once the game finishes; the normal replay files are then written.

What is saved: the full rules state, the event log (so replays and the hash still cover the whole game),
every notebook including your notes, illegal-move counts, ponder stats, and each agent's private state
(baseline bots: which cards they have shown to whom; expert bot: its shown-card memory; LLM agents: usage
stats, cost, last plan and fallback state; all bots: their RNG). A human seat has nothing to save beyond
its notebook. The file is plain JSON (`format: 2`) and **contains the solution and all hands** - treat it like
the unredacted replay.

Programmatic: `gm.save(path, agents)`, `gm = GameManager.load(path)`, `gm.restore_agents(agents)` and
`run_game(gm, agents, autosave=path, stop=callable)`; agents implement `export_state()` / `import_state()`
(`PlayerAgent` provides a default that serialises `self.rng`).

## Plain CLI (`--ui cli`)
Same information as Rich tables and a numbered menu (`Your action #:`). Used for the reproducible transcript
in `demo_game.md`; every prompt is a plain `input()` so it works over SSH or in a pipe.

## Coach mode (`h`)

Press `h` at any time in the TUI to toggle the coach panel: number of envelope combinations still consistent
with *your* notebook, the most likely one, up to four forced facts from the exact solver ("P3 must hold
Lounge"), and what `baseline:expert` would do from your seat. It is strictly opt-in: nothing is written to
your notebook, and every activation is logged as an `agent_note` (`coach_mode_on`) in the replay so a
coached game is distinguishable from an uncoached one.

## Replay viewer (`clue replay FILE --tui`)

Steps through a replay on the board: `n`/`→` next, `b`/`←` previous, `space` autoplay, `+`/`-` speed,
`g`/`G` start/end, `v` cycles the viewer (omniscient → P1 → P2 …) applying the same redaction as the
manager, so you can see exactly what each seat knew when.

## Spectating is omniscient

`--spectate` (all-AI game) shows everything: the event log prints every card actually shown, the status bar
names the envelope, and the notebook grid is replaced by an **All hands** table — the true holder of every
card next to what each seat currently knows (`mine` / holder / `?✘✘` = number of seats ruled out / `env!` =
that seat has deduced the envelope). Press `v` to step through each seat's private perspective
(P1 → P2 → … → omniscient); the Deductions and Coach panels follow the selected seat, and in omniscient mode
they follow whoever is acting.

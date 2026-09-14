# Variance-reduction variants (opt-in)

Classic Clue is noisy: the deal, the dice and who sits where decide a large share of games, so it takes many
games to tell two agents apart. These six options each cut one source of luck. **All are off by default** — the
classic rules (RULES_SPEC.md) are unchanged unless you switch something on — and they compose freely.

| | Variant | Where it lives | Switch |
|---|---|---|---|
| A | Duplicate deals (eval) | `clue/eval/tournament.py` | `clue tournament --duplicate`, web tournament page ☑ *duplicate deals* |
| B | Team mode | `GameConfig.teams` | YAML `teams: [[P1,P3],[P2,P4]]`, `--variants teams[=K]`, lobby *teams* |
| C | Private disproofs | `GameConfig.private_disproofs` | YAML `private_disproofs: true`, `--variants private`, lobby ☑ |
| D | Skip-turn penalty | `GameConfig.wrong_accusation`, `accusation_penalty_turns` | YAML `wrong_accusation: skip_turns`, `--variants skip[=N]`, lobby *wrong accusation* |
| E | Shuffled seats | `GameConfig.shuffle_seats` | YAML `shuffle_seats: true`, `--variants shuffle`, lobby ☑ |
| F | Table size | `GameConfig.num_players` | just play fewer seats (guidance below) |

`--variants` takes a comma list, e.g. `clue play --players human,baseline:expert,baseline,baseline --variants private,skip=2`.
The rules engine enforces every variant (`legal_actions` / `apply_action`), the manager keeps redaction server-side,
and every UI (CLI, TUI, web) just renders the events it is allowed to see — no UI-side rule logic.

---

## A. Duplicate deals (tournament only)

Like duplicate bridge: a block of `len(players)` games shares one seed (same deal, same dice stream) while the
agents are cyclically rotated through the seats, so every agent plays every deal from every seat.
`games` is rounded up to whole blocks. Besides the usual table the report gets a `duplicate` section:

* `win_share` – mean over deals of the fraction of that block's games the agent won;
* `paired_diff ± se` – difference vs the strongest other agent **computed per deal and then averaged**, so the
  deal's difficulty cancels; `se` is the standard error of that paired difference (deals are the samples).

```bash
clue tournament --players baseline:expert,baseline:heuristic,baseline:heuristic --games 30 --duplicate -w 0
```

Implementation: `_play_one(..., rotation=r)` shifts the spec list by `r`; `duplicate_stats()` builds the pairing.
It replaces the default per-game seat shuffle (`rotate_seats`) inside duplicate blocks.

## B. Team mode

`teams` partitions the player ids (every player in exactly one team; validated in `new_game`). Effects:

* teammates' hands are merged into each other's notebook (`Notebook.team`, `my_hand`, `known_holder`) and shown
  in `observation["you"]["team_hands"]`;
* the disproof round **skips teammates** of the suggester (they already know each other's cards);
* the `disproved` event is private to both teams involved (card visible to suggester's team and shower's team);
* a correct accusation wins for the whole team — `game_over.team`, `summary()["winning_team"]`; a wrong one only
  punishes the accuser (elimination or D's penalty) and the teammate plays on.

Seats still alternate around the table (teams `[P1,P3]`/`[P2,P4]` is the natural round-robin split that
`--variants teams` produces), which keeps the disproof geometry fair.

## C. Private disproofs

Only the suggester (and their team) and the player concerned learn **who passed** and **who showed**. Bystanders
receive a `disproved` event with `player: null` ("someone showed a card to P2") and never receive
`cannot_disprove` / `can_disprove` events at all: those carry `Event.hidden = True` and `private_to`, and
`GameManager`, the runner, the TUI, the web session and `export_replay(viewer)` all filter on `Event.visible_to(pid)`.
The omniscient audit log (`export_replay(None)`, replay hash) is complete as always.

This removes most of the "free" inference that a passive third party gets from watching other people's
suggestions, so information advantage comes mainly from your own questions — the game becomes closer to a
sequence of private queries, i.e. much less dependent on turn order.

## D. Skip-turn penalty

`wrong_accusation: skip_turns` — a wrong accusation no longer eliminates: the accuser sits out their next
`accusation_penalty_turns` (default 2) turns (`penalised` event, then `turn_skipped` events as those turns come
round; each skipped turn still increments `turn_number`). They keep disproving in between. `eliminate` is the
classic rule. Rationale: elimination turns a 3–4 player game into a 2-player one and makes an early gamble a
huge swing; a time penalty keeps the table full.

## E. Shuffled seats

`shuffle_seats: true` — `new_game` shuffles the seating order with the game RNG (seeded, so replays are still
deterministic; P1 is no longer guaranteed to be Miss Scarlet / first). Use it for casual play; tournaments
already do this per game (`rotate_seats=True`) or use A.

## F. Table size

Variance grows with table size (more hands = more scattered information, more turns between your own turns,
more chances a third party stumbles onto the answer). For measuring agent strength prefer **3–4 seats** and pair
with A; for the large (12-player) edition expect very noisy single games and lean on duplicate blocks.

---

## Agents and variants

* Baselines/expert/solver are agnostic: they read the notebook (which already contains team hands and only the
  facts the viewer is entitled to) and `hand_size`s from the observation.
* LLM agents get a `house_rules` list in the observation describing any variant in effect (`variant_notes()` in
  `clue/agents/llm_agent.py`).
* The opponent model ignores `disproved` events whose shower is unknown.

## Tests

`tests/test_variants.py` covers: defaults unchanged; C event privacy at the engine, manager, replay and notebook
level plus save/load equality; D penalty and the "everyone penalised" no-hang case; B validation, teammate skipping,
merged hands and team win credit; E seeded permutation; A block rounding and paired statistics; `--variants`
grammar and YAML keys.

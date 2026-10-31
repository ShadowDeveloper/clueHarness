# Observation schema

`GameManager.get_observation(player_id)` returns a JSON-serialisable dict. It is the **only** thing an agent
sees (plus the `legal_actions` list handed to `choose_action`). It is built per viewer and never contains
another player's hand, the envelope, or a card shown between two other players.

| Key | Type | Description |
|---|---|---|
| `you.id` / `you.name` / `you.suspect_token` | str | Your stable seat id, optional configured display name, and edition-specific token |
| `you.team`, `you.team_hands` | list / dict or null | Set only when teams are enabled; contains teammate ids and their hands |
| `you.skip_turns` | int | Remaining penalty turns (zero when not penalized) |
| `you.hand` | list[str] | Your private cards (sorted) |
| `you.position` | str | Room name or `"row,col"` |
| `you.in_room`, `you.eliminated`, `you.may_suggest` | bool | `may_suggest` = entered a room this turn or was summoned since your last turn |
| `board.token_positions` | dict[suspect → pos] | All suspect tokens in this edition (unused tokens stay on their start squares; six in Classic/Modern, twelve in Large) |
| `board.weapon_positions` | dict[weapon → room] | Cosmetic |
| `board.players[]` | id, suspect_token, position, eliminated, **hand_size**, team | Never hands; `team` is `null` unless teams are enabled |
| `board.secret_passages` | dict | Edition-specific passage pairs (e.g. Classic/Modern: Lounge⇄Conservatory and Kitchen⇄Study) |
| `board.your_legal_moves` | list[str] | Destinations after a roll (empty otherwise) |
| `turn.number`, `turn.current_player`, `turn.phase`, `turn.roll` | | `phase ∈ move, suggest, accuse, disprove, end` |
| `turn.pending_suggestion` | obj or null | Present while a disproof is pending |
| `turn.you_are_acting` | bool | |
| `public_history[]` | list[event] | Redacted events (see `replay_format.md`); `game_start` is omitted |
| `notebook` | Notebook | Mechanically derived facts — see below |
| `legal_actions[]` | list[Action] | Concrete legal actions **except** accusations; accusation combinations are supplied by the current `cards` lists and validated separately |
| `can_accuse` | bool | If true, any `{type: accuse, suspect, weapon, room}` is legal |
| `cards.suspects / weapons / rooms / faceup` | lists | Canonical spellings for this edition |
| `config` | full `GameConfig.model_dump()` | edition, dice, deal_remainder, num_players, max_turns, teams, private_disproofs, wrong_accusation, accusation_penalty_turns, shuffle_seats |

All configured players also receive `board.players[].team` (null with teams disabled). The example below is an ordinary
Classic, non-team observation; when teams are enabled, `you.team` and `you.team_hands` are populated and the
board/config fields reflect the selected edition and rules. The serialized `config` always includes every
`GameConfig` field, including defaults and null values; this short schema table summarizes the fields most
relevant to agents, not a reduced config object.

Two non-serialisable handles are attached by the runner for in-process agents and stripped before any
prompt: `_notebook_obj` (the live `Notebook` for the symbolic tools) and `_manager` (for tool-call logging).
`last_error` is added when a previous reply was rejected.

## Notebook fields
| Field | Meaning |
|---|---|
| `my_hand`, `faceup` | Cards known not in the solution; `my_hand` also includes teammates' hands when teams are enabled |
| `known_holder` | card → player, for your hand/team hands and cards shown **to you** |
| `not_held` | player → cards they provably lack (failed to disprove; or a suggestion nobody disproved) |
| `has_one_of[]` | `{player, cards, turn, suggester}` — player disproved but not to you |
| `unrefuted_suggestions[]` | suggestions nobody could disprove |
| `suggestions_made`, `disproof_counts` | per-player counters |
| `my_suggestions[]` | your suggestions with `shown` / `by` filled in |
| `notes[]` | free text appended via the `update_notebook` tool |

## Example (P1, seed 42, start of their 3rd turn; history truncated to 6 events)
```json
{
 "you": {
  "id": "P1",
  "name": null,
  "suspect_token": "Miss Scarlet",
  "hand": [
   "Col. Mustard",
   "Lead Pipe",
   "Mr. Green",
   "Revolver",
   "Wrench"
  ],
  "position": "Conservatory",
  "in_room": true,
  "eliminated": false,
  "skip_turns": 0,
  "may_suggest": false,
  "team": null,
  "team_hands": null
 },
 "board": {
  "token_positions": {
   "Miss Scarlet": "Conservatory",
   "Col. Mustard": "Ballroom",
   "Mrs. White": "10,8",
   "Mr. Green": "Ballroom",
   "Mrs. Peacock": "Lounge",
   "Prof. Plum": "Conservatory"
  },
  "weapon_positions": {
   "Candlestick": "Dining Room",
   "Dagger": "Conservatory",
   "Lead Pipe": "Hall",
   "Revolver": "Ballroom",
   "Rope": "Lounge",
   "Wrench": "Ballroom"
  },
  "players": [
   {
    "id": "P1",
    "suspect_token": "Miss Scarlet",
    "position": "Conservatory",
    "eliminated": false,
    "hand_size": 5,
    "team": null
   },
   {
    "id": "P2",
    "suspect_token": "Col. Mustard",
    "position": "Ballroom",
    "eliminated": false,
    "hand_size": 5,
    "team": null
   },
   {
    "id": "P3",
    "suspect_token": "Mrs. White",
    "position": "10,8",
    "eliminated": false,
    "hand_size": 4,
    "team": null
   },
   {
    "id": "P4",
    "suspect_token": "Mr. Green",
    "position": "Ballroom",
    "eliminated": false,
    "hand_size": 4,
    "team": null
   }
  ],
  "secret_passages": {
   "Lounge": "Conservatory",
   "Conservatory": "Lounge",
   "Kitchen": "Study",
   "Study": "Kitchen"
  },
  "your_legal_moves": []
 },
 "turn": {
  "number": 8,
  "current_player": "P1",
  "phase": "move",
  "roll": null,
  "pending_suggestion": null,
  "you_are_acting": true
 },
 "public_history": [
  {
   "type": "roll",
   "turn": 7,
   "player": "P4",
   "dice": [
    1,
    4
   ],
   "total": 5
  },
  {
   "type": "move",
   "turn": 7,
   "player": "P4",
   "from": "4,16",
   "to": "Ballroom"
  },
  {
   "type": "suggest",
   "turn": 7,
   "player": "P4",
   "suspect": "Col. Mustard",
   "weapon": "Wrench",
   "room": "Ballroom"
  },
  {
   "type": "can_disprove",
   "turn": 7,
   "player": "P1",
   "suggester": "P4"
  },
  {
   "type": "disproved",
   "turn": 7,
   "player": "P1",
   "suggester": "P4",
   "disprover": "P1",
   "card": "Col. Mustard"
  },
  {
   "type": "turn_start",
   "turn": 8,
   "player": "P1"
  }
 ],
 "notebook": {
  "viewer": "P1",
  "my_hand": [
   "Col. Mustard",
   "Lead Pipe",
   "Mr. Green",
   "Revolver",
   "Wrench"
  ],
  "faceup": [],
  "known_holder": {
   "Col. Mustard": "P1",
   "Lead Pipe": "P1",
   "Mr. Green": "P1",
   "Revolver": "P1",
   "Wrench": "P1",
   "Rope": "P2",
   "Dagger": "P2"
  },
  "not_held": {
   "P4": [
    "Prof. Plum",
    "Revolver",
    "Ballroom"
   ]
  },
  "has_one_of": [],
  "unrefuted_suggestions": [],
  "suggestions_made": {
   "P1": 2,
   "P3": 1,
   "P4": 1
  },
  "disproof_counts": {
   "P2": 2,
   "P1": 2
  },
  "my_suggestions": [
   {
    "turn": 0,
    "cards": [
     "Mrs. Peacock",
     "Rope",
     "Lounge"
    ],
    "shown": "Rope",
    "by": "P2"
   },
   {
    "turn": 4,
    "cards": [
     "Prof. Plum",
     "Dagger",
     "Conservatory"
    ],
    "shown": "Dagger",
    "by": "P2"
   }
  ],
  "notes": []
 },
 "legal_actions": [
  {
   "type": "roll",
   "player": "P1"
  },
  {
   "type": "passage",
   "player": "P1"
  }
 ],
 "can_accuse": true,
 "cards": {
  "suspects": [
   "Miss Scarlet",
   "Col. Mustard",
   "Mrs. White",
   "Mr. Green",
   "Mrs. Peacock",
   "Prof. Plum"
  ],
  "weapons": [
   "Candlestick",
   "Dagger",
   "Lead Pipe",
   "Revolver",
   "Rope",
   "Wrench"
  ],
  "rooms": [
   "Hall",
   "Lounge",
   "Dining Room",
   "Kitchen",
   "Ballroom",
   "Conservatory",
   "Billiard Room",
   "Library",
   "Study"
  ],
  "faceup": []
 },
 "config": {
  "edition": "classic",
  "dice": 2,
  "deal_remainder": "uneven",
  "num_players": 4,
  "max_turns": 400,
  "teams": null,
  "private_disproofs": false,
  "wrong_accusation": "eliminate",
  "accusation_penalty_turns": 2,
  "shuffle_seats": false
 }
}

```

## LLM view
`LLMPlayerAgent` sends the same object, minus `_`-prefixed keys, with `public_history` truncated to the last
40 events, a placeholder `suggest` entry in `legal_actions`, and — when tools are enabled — an `analysis`
block: `unseen_cards`, `posterior` (`n_possible`, top `combos`, per-card `cards`, `best`, `best_prob`,
`exact`), `accusation_check` (also reports `exact`), `certain_facts`, `opponent_threat`,
`top_suggestions[]` when a suggestion is legal, and `recommended_action`. For Large edition, candidate counts and
probabilities are estimates; see `tools.md`.

# Pondering mode (between your turns)

It is NOT your turn. Other players are acting. Use this time to update your understanding of the case so
that your next decision is fast and well-founded.

You are in a short think → tool → think loop. Each round, reply with ONE JSON object:

- Call a tool:  `{"thought": "<why>", "tool": "<name>", "args": {...}}`
  Tools: `get_unseen_cards`, `get_possible_solutions`, `solution_probabilities`,
  `suggestion_ev {suspect, weapon, room}`, `can_accuse_confidently {threshold}`, `update_notebook {note}`.
- Or finish:    `{"thought": "<summary>", "plan": "<what you intend to do on your turn>",
                  "notes": ["<short deduction to remember>", ...], "done": true}`

Guidance
- Start from `ponder_summary`/`notebook.notes` so you don't redo work you already did.
- Turn public events into hard facts: "P3 could not disprove X/Y/Z" → P3 holds none of them.
- Cross `has_one_of` constraints with cards you know to pin down single cards.
- Record every new certainty as a note (they are saved to your notebook).
- Prepare a plan: which room to head for, which suggestion to make there, and whether an accusation is
  already justified (only if `can_accuse_confidently` says so).
- You may be interrupted at any time when new information arrives or your turn begins; anything you've
  already noted is kept. Keep rounds short (≤ 4 tool calls).

# Pondering mode (between your turns)

It is NOT your turn. Other players are acting. Use this time to update your understanding of the case so
that your next decision is fast and well-founded.

You are in a short think → tool → think loop. Each round, reply with ONE JSON object:

- Call a tool: `{"thought": "<why>", "tool": "<name>", "args": {...}}`
  Available tools: `get_unseen_cards`, `get_possible_solutions`, `solution_probabilities`,
  `holder_probabilities`, `hard_deductions`, `opponent_threat`, `suggestion_ev {suspect, weapon, room}`,
  `can_accuse_confidently {threshold}`, and `update_notebook {note}`.
- Or finish: `{"thought": "<summary>", "plan": "<what you intend to do on your turn>",
  "notes": ["<short deduction to remember>", ...], "done": true}`

Guidance
- Start from `ponder_summary` / `notebook.notes` so you do not redo work already recorded.
- Turn events visible in `public_history` into facts: a visible "could not disprove" event means that player
  holds none of those three cards. Respect `config` and `house_rules`; private-disproof games hide some events.
- Cross `has_one_of` constraints with cards you know to pin down single cards.
- Record new certainties as notes; `update_notebook` and the final `notes` list are merged into your notebook.
- Solver output is marked exact or approximate. Large-edition posterior values are estimates, and its candidate
  list may include triples not verified by a complete deal; do not treat a singleton sampled list as proof.
  `hard_deductions` contains sound forced facts.
- Prepare a plan: which room to head for, which suggestion to make there, and whether an accusation is
  justified. Check whether confidence is exact before relying on it.
- You may be interrupted at any time when new information arrives or your turn begins; anything you have
  already noted is kept. Keep rounds short (≤ 4 tool calls).

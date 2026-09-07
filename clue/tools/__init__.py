"""Symbolic deduction tools (no LLM)."""

from clue.tools.deduction import (
    TOOL_SPECS,
    best_suggestion,
    can_accuse_confidently,
    get_possible_solutions,
    get_unseen_cards,
    hard_deductions,
    holder_probabilities,
    solution_probabilities,
    suggestion_ev,
    update_notebook,
)
from clue.tools.opponent import opponent_threat
from clue.tools.solver import Solution, solve

__all__ = [
    "Solution",
    "TOOL_SPECS",
    "best_suggestion",
    "can_accuse_confidently",
    "get_possible_solutions",
    "get_unseen_cards",
    "hard_deductions",
    "holder_probabilities",
    "opponent_threat",
    "solve",
    "solution_probabilities",
    "suggestion_ev",
    "update_notebook",
]

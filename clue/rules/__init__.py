"""Pure rules engine for Classic US Clue. Never imports LLM or I/O code."""

from clue.rules.engine import apply_action, can_accuse, check_winner, is_legal, legal_actions, new_game
from clue.rules.state import Action, Event, GameConfig, GameState, IllegalAction, PlayerState

__all__ = [
    "Action",
    "Event",
    "GameConfig",
    "GameState",
    "IllegalAction",
    "PlayerState",
    "apply_action",
    "can_accuse",
    "check_winner",
    "is_legal",
    "legal_actions",
    "new_game",
]

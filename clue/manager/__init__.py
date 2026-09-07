"""Game State Manager: orchestration, privacy, replay. Contains no strategy text or LLM code."""

from clue.manager.game_manager import GameManager, LogRecord, PlayerSpec
from clue.manager.notebook import Notebook

__all__ = ["GameManager", "LogRecord", "Notebook", "PlayerSpec"]

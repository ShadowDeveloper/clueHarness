"""Human seat driven by HTTP: the game thread blocks on a queue until the browser answers (same pattern as the TUI)."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any

from clue.agents.base import PlayerAgent
from clue.manager.runner import GameInterrupted
from clue.rules import Action


@dataclass
class PendingRequest:
    request_id: int
    player: str
    kind: str  # "action" | "card"
    observation: dict[str, Any]
    legal: list[Action] = field(default_factory=list)
    cards: list[str] = field(default_factory=list)
    reply: queue.Queue[Any] = field(default_factory=queue.Queue)


class WebHumanAgent(PlayerAgent):
    kind = "human"

    def __init__(self, player_id: str) -> None:
        super().__init__(player_id)
        self.on_request: Any = None  # set by the session: callable(PendingRequest)
        self._seq = 0
        self._lock = threading.Lock()

    def _ask(self, kind: str, obs: dict[str, Any], legal: list[Action] | None = None, cards: list[str] | None = None) -> Any:
        with self._lock:
            self._seq += 1
            req = PendingRequest(self._seq, self.id, kind, obs, legal or [], cards or [])
        assert self.on_request is not None, "WebHumanAgent not attached to a session"
        self.on_request(req)
        ans = req.reply.get()
        if ans is None:
            raise GameInterrupted()
        return ans

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        act = self._ask("action", observation, legal=legal_actions)
        assert isinstance(act, Action)
        return act

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        if len(cards_that_can_disprove) == 1:
            return cards_that_can_disprove[0]
        return str(self._ask("card", observation, cards=cards_that_can_disprove))

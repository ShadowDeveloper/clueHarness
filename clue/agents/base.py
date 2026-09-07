"""Unified PlayerAgent interface. All seats (human, llm, baseline) implement it."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from clue.rules import Action


class PonderInterrupted(Exception):
    """Raised inside `ponder()` by `ctx.check()` when the manager asks the agent to stop."""


class PonderContext:
    """Handed to `PlayerAgent.ponder`. Cooperative interruption + sandboxed tools.

    - `check()` raises PonderInterrupted once the manager has requested a stop (new information
      arrived or it is this player's turn). Call it between expensive steps (tool calls, LLM calls).
    - `tool(name, **args)` runs a symbolic tool on a *snapshot* of the player's notebook and logs it.
    - `note(text)` queues a notebook note; notes are merged into the real notebook when the session ends.
    - `reason` is set when a stop is requested: "new_information" | "your_turn" | "game_over".
    """

    def __init__(self, player_id: str, tool_fn: Callable[..., Any]) -> None:
        self.player_id = player_id
        self._stop = threading.Event()
        self._tool_fn = tool_fn
        self.reason: str | None = None
        self.notes: list[str] = []
        self.tool_calls = 0
        self.rounds = 0

    def request_stop(self, reason: str) -> None:
        if self.reason is None:
            self.reason = reason
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def check(self) -> None:
        if self._stop.is_set():
            raise PonderInterrupted(self.reason or "stop")

    def wait(self, seconds: float) -> None:
        """Sleep that returns early (and raises) on interrupt."""
        if self._stop.wait(seconds):
            raise PonderInterrupted(self.reason or "stop")

    def tool(self, name: str, **args: Any) -> Any:
        self.check()
        self.tool_calls += 1
        return self._tool_fn(name, **args)

    def note(self, text: str) -> None:
        self.notes.append(text)


class PlayerAgent(ABC):
    id: str
    kind: str  # "human" | "llm" | "baseline"

    def __init__(self, player_id: str) -> None:
        self.id = player_id

    @abstractmethod
    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        """Pick a main action. `legal_actions` excludes the 324 accusation permutations;
        an accusation is legal whenever observation['can_accuse'] is True."""

    @abstractmethod
    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        """Pick exactly one card from `cards_that_can_disprove` to reveal to the suggester."""

    def on_event(self, event: dict[str, Any]) -> None:  # optional hook (e.g. for humans to see messages)
        return None

    # ---- save / resume ---------------------------------------------------------------------
    def export_state(self) -> dict[str, Any]:
        """JSON-able private memory (RNG state, cards shown, plans...). Default: RNG if present, else nothing.

        The notebook is NOT part of this: the manager rebuilds every notebook from the event log on load.
        """
        out: dict[str, Any] = {}
        rng = getattr(self, "rng", None)
        if rng is not None:
            out["rng"] = _rng_dump(rng)
        return out

    def import_state(self, state: dict[str, Any]) -> None:
        rng = getattr(self, "rng", None)
        if rng is not None and "rng" in state:
            _rng_load(rng, state["rng"])

    # ---- parallel thinking (optional) ------------------------------------------------------
    supports_ponder: bool = False

    def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
        """Think while others act. Runs in a background thread on a snapshot observation.

        Must be side-effect free apart from `ctx.note()` / caching on `self`; must call `ctx.check()`
        regularly and return promptly once interrupted. Return a small JSON-able summary for the log.
        """
        return {}


def _rng_dump(rng: Any) -> list[Any]:
    v, s, g = rng.getstate()
    return [v, list(s), g]


def _rng_load(rng: Any, data: list[Any]) -> None:
    v, s, g = data
    rng.setstate((v, tuple(s), g))

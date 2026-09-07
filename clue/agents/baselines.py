"""Scripted baseline bots: BaselineRandomBot and BaselineHeuristicBot (no LLM)."""

from __future__ import annotations

import random
from typing import Any

from clue.agents.base import PlayerAgent, PonderContext
from clue.manager.notebook import Notebook
from clue.rules import Action
from clue.rules import board as B
from clue.tools import best_suggestion, can_accuse_confidently, get_possible_solutions


def _nb(observation: dict[str, Any]) -> Notebook:
    nb = observation.get("_notebook_obj")
    if isinstance(nb, Notebook):
        return nb
    return Notebook(**observation["notebook"])


class BaselineRandomBot(PlayerAgent):
    kind = "baseline"

    def __init__(self, player_id: str, seed: int = 0, accuse_prob: float = 0.02) -> None:
        super().__init__(player_id)
        self.rng = random.Random(seed)
        self.accuse_prob = accuse_prob

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        if observation["can_accuse"] and self.rng.random() < self.accuse_prob:
            c = observation["cards"]
            return Action(type="accuse", player=self.id, suspect=self.rng.choice(c["suspects"]), weapon=self.rng.choice(c["weapons"]), room=self.rng.choice(c["rooms"]))
        return self.rng.choice(legal_actions)

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        return self.rng.choice(cards_that_can_disprove)


class BaselineHeuristicBot(PlayerAgent):
    """Deterministic deduction bot.

    - Accuse when exactly one consistent solution remains (or posterior >= threshold).
    - Move toward the nearest room whose card is still unknown; prefer passages.
    - Suggest the unknown-maximising (suspect, weapon) in the current room.
    - Show the card already revealed to that suggester if possible (leak least).
    """

    kind = "baseline"
    supports_ponder = True

    def __init__(self, player_id: str, seed: int = 0, threshold: float = 1.0) -> None:
        super().__init__(player_id)
        self.rng = random.Random(seed)
        self.threshold = threshold
        self.shown: dict[str, set[str]] = {}
        self.plan: dict[str, Any] = {}

    def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
        """Between turns: precompute the candidate set and a target room; note any newly-forced facts."""
        ctx.rounds += 1
        sols = ctx.tool("get_possible_solutions")
        ctx.check()
        unseen = ctx.tool("get_unseen_cards")
        plan: dict[str, Any] = {"n_possible": len(sols), "target_rooms": unseen["rooms"][:3]}
        if len(sols) == 1:
            plan["accuse"] = sols[0]
            ctx.note(f"Only one consistent solution left: {' / '.join(sols[0])}")
        elif len(sols) <= 6:
            ctx.check()
            post = ctx.tool("solution_probabilities")
            plan["best"] = post.get("best")
            plan["best_prob"] = post.get("best_prob")
        for cat in ("suspects", "weapons", "rooms"):
            if len(unseen[cat]) == 1:
                ctx.note(f"{cat[:-1]} must be {unseen[cat][0]}")
        self.plan = plan
        return plan

    def _players(self, obs: dict[str, Any]) -> list[str]:
        return [p["id"] for p in obs["board"]["players"]]

    def _sizes(self, obs: dict[str, Any]) -> dict[str, int]:
        return {p["id"]: p["hand_size"] for p in obs["board"]["players"]}

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        obs = observation
        nb = _nb(obs)
        players, sizes = self._players(obs), self._sizes(obs)
        edition = obs["config"]["edition"]
        types = {a.type for a in legal_actions}
        if obs["can_accuse"]:
            sols = get_possible_solutions(nb, players, sizes, edition)
            if len(sols) == 1:
                s, w, r = sols[0]
                return Action(type="accuse", player=self.id, suspect=s, weapon=w, room=r)
            if self.threshold < 1.0 and len(sols) <= 6:
                verdict = can_accuse_confidently(nb, players, self.threshold, sizes, edition)
                if verdict["accuse"]:
                    s, w, r = verdict["best"]
                    return Action(type="accuse", player=self.id, suspect=s, weapon=w, room=r)
        if "suggest" in types:
            room = obs["you"]["position"]
            s, w = best_suggestion(nb, players, self.id, room, edition, self.rng)
            return Action(type="suggest", player=self.id, suspect=s, weapon=w, room=room)
        unknown_rooms = [r for r in obs["cards"]["rooms"] if r not in nb.known_not_in_solution()]
        if "passage" in types:
            dest = B.SECRET_PASSAGES[obs["you"]["position"]]
            if dest in unknown_rooms or not unknown_rooms:
                return Action(type="passage", player=self.id)
        if "roll" in types:
            return Action(type="roll", player=self.id)
        if "move" in types:
            moves = [a for a in legal_actions if a.type == "move"]
            rooms = [a for a in moves if B.is_room(a.to or "")]
            pref = [a for a in rooms if a.to in unknown_rooms]
            if pref:
                return self.rng.choice(pref)
            if rooms:
                return self.rng.choice(rooms)
            # head toward the nearest unknown room
            targets = unknown_rooms or list(obs["cards"]["rooms"])
            best = min(moves, key=lambda a: self._dist_to_rooms(a.to or "", targets))
            return best
        if "end_turn" in types:
            return Action(type="end_turn", player=self.id)
        return legal_actions[0]

    @staticmethod
    def _dist_to_rooms(pos: str, rooms: list[str]) -> int:
        if B.is_room(pos):
            return 0
        cell = B.parse_sq(pos)
        best = 999
        for room in rooms:
            for door in B.DOORS[room]:
                best = min(best, abs(cell[0] - door[0]) + abs(cell[1] - door[1]))
        return best

    def export_state(self) -> dict[str, Any]:
        return {**super().export_state(), "shown": {k: sorted(v) for k, v in self.shown.items()}}

    def import_state(self, state: dict[str, Any]) -> None:
        super().import_state(state)
        self.shown = {k: set(v) for k, v in state.get("shown", {}).items()}

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        suggester = observation["turn"]["pending_suggestion"]["suggester"]
        already = self.shown.setdefault(suggester, set())
        for c in cards_that_can_disprove:
            if c in already:
                return c
        # otherwise show the card of the category we have most of (least informative)
        card = sorted(cards_that_can_disprove)[0]
        already.add(card)
        return card

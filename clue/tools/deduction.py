"""Symbolic / math deduction tools over a Notebook. Pure functions, no LLM.

These are exposed to LLM agents as callable tools AND pre-computed into the observation, and
are also used by the baseline bots. All reasoning is over *public + own-private* info only.
`get_possible_solutions` / `solution_probabilities` are EXACT (see clue/tools/solver.py).
"""

from __future__ import annotations

import random
from typing import Any

from clue.manager.notebook import Notebook
from clue.rules.cards import ROOMS, WEAPONS, suspects
from clue.tools.solver import hard_deductions as solver_hard_deductions
from clue.tools.solver import solve

Combo = tuple[str, str, str]


def get_unseen_cards(nb: Notebook, edition: str = "classic") -> dict[str, list[str]]:
    """Cards not in your hand, not face-up, and not shown to you — per category."""
    known = nb.known_not_in_solution()
    return {
        "suspects": [c for c in suspects(edition) if c not in known],  # type: ignore[arg-type]
        "weapons": [c for c in WEAPONS if c not in known],
        "rooms": [c for c in ROOMS if c not in known],
    }


def _hand_sizes(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None) -> dict[str, int]:
    if hand_sizes:
        return hand_sizes
    base, rem = divmod(18 - len(nb.faceup), len(players))
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(players)}


def get_possible_solutions(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> list[Combo]:
    """All (suspect, weapon, room) combos for which at least one full hand assignment is consistent (exact)."""
    return solve(nb, players, hand_sizes, edition).possible


def solution_probabilities(
    nb: Notebook,
    players: list[str],
    hand_sizes: dict[str, int] | None = None,
    edition: str = "classic",
    samples: int = 0,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Exact posterior over envelope combos and cards, assuming all consistent deals are equally likely.

    (`samples`/`rng` are accepted for backwards compatibility and ignored.)
    """
    sol = solve(nb, players, hand_sizes, edition)
    if not sol.combos:
        return {"combos": {}, "cards": {}, "n_possible": 0}
    total = sol.n_assignments
    ranked = sorted(sol.combos.items(), key=lambda kv: -kv[1])
    best, best_prob = sol.best
    cards = {c: round(p, 4) for c, p in sorted(sol.card_probs.items(), key=lambda kv: -kv[1]) if p > 0}
    return {
        "n_possible": len(sol.combos),
        "combos": {" | ".join(c): round(n / total, 4) for c, n in ranked[:10]},
        "cards": cards,
        "best": list(best) if best else None,
        "best_prob": round(best_prob, 4),
        "exact": True,
    }


def holder_probabilities(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> dict[str, dict[str, float]]:
    """P(card is held by player | evidence) for every card; includes the 'envelope' pseudo-holder."""
    return solve(nb, players, hand_sizes, edition).holder_probs


def hard_deductions(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> list[str]:
    """Certainties provable from the evidence but not yet written in the notebook (coach mode / bots)."""
    return solver_hard_deductions(solve(nb, players, hand_sizes, edition), nb)


def suggestion_ev(nb: Notebook, players: list[str], me: str, suspect: str, weapon: str, room: str, edition: str = "classic") -> dict[str, Any]:
    """Expected information value of a suggestion (heuristic, 0..1 scale components)."""
    cards = [suspect, weapon, room]
    known = nb.known_not_in_solution()
    novelty = sum(1 for c in cards if c not in known) / 3.0
    order = players[players.index(me) + 1 :] + players[: players.index(me)]
    possible_disprovers = 0
    first_unknown = None
    for p in order:
        excluded = set(nb.not_held.get(p, []))
        could = [c for c in cards if c not in excluded and nb.known_holder.get(c) not in (me,)]
        if could:
            possible_disprovers += 1
            if first_unknown is None and any(nb.known_holder.get(c) is None for c in could):
                first_unknown = p
    # Prefer suggestions where the first potential disprover holds none of our own cards
    # (so what they show is new to us). Score in [0,1].
    mine_in = sum(1 for c in cards if c in nb.my_hand)
    score = 0.5 * novelty + 0.3 * (possible_disprovers / max(1, len(players) - 1)) + 0.2 * (1 - mine_in / 3)
    return {
        "novelty": round(novelty, 3),
        "possible_disprovers": possible_disprovers,
        "first_unknown_disprover": first_unknown,
        "own_cards_included": mine_in,
        "score": round(score, 3),
    }


def can_accuse_confidently(nb: Notebook, players: list[str], threshold: float = 0.9, hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> dict[str, Any]:
    post = solution_probabilities(nb, players, hand_sizes, edition)
    if post["n_possible"] == 0:
        return {"accuse": False, "reason": "notebook inconsistent", "best": None, "confidence": 0.0}
    return {
        "accuse": post["best_prob"] >= threshold,
        "best": post["best"],
        "confidence": post["best_prob"],
        "n_possible": post["n_possible"],
        "threshold": threshold,
    }


def update_notebook(nb: Notebook, note: str) -> dict[str, Any]:
    """Append a structured free-text deduction to the agent's notes."""
    nb.notes.append(note)
    return {"ok": True, "n_notes": len(nb.notes)}


def best_suggestion(nb: Notebook, players: list[str], me: str, room: str, edition: str = "classic", rng: random.Random | None = None) -> tuple[str, str]:
    """Pick the (suspect, weapon) that maximises suggestion_ev in `room`."""
    rng = rng or random.Random(0)
    best: list[tuple[float, str, str]] = []
    for s in suspects(edition):  # type: ignore[arg-type]
        for w in WEAPONS:
            sc = suggestion_ev(nb, players, me, s, w, room, edition)["score"]
            best.append((sc, s, w))
    best.sort(reverse=True)
    top = [b for b in best if b[0] >= best[0][0] - 1e-9]
    _, s, w = rng.choice(top)
    return s, w


TOOL_SPECS: list[dict[str, Any]] = [
    {"name": "get_unseen_cards", "description": "Cards not in your hand, not face-up and not shown to you, by category.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_possible_solutions", "description": "All (suspect, weapon, room) combos consistent with everything you know.", "parameters": {"type": "object", "properties": {}}},
    {"name": "solution_probabilities", "description": "Approximate posterior over cards and top combos.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "suggestion_ev",
        "description": "Information value of suggesting (suspect, weapon) in your current room.",
        "parameters": {"type": "object", "properties": {"suspect": {"type": "string"}, "weapon": {"type": "string"}, "room": {"type": "string"}}, "required": ["suspect", "weapon", "room"]},
    },
    {"name": "update_notebook", "description": "Append a deduction note to your private notebook.", "parameters": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}},
    {"name": "can_accuse_confidently", "description": "Best guess + confidence vs a threshold.", "parameters": {"type": "object", "properties": {"threshold": {"type": "number"}}}},
    {
        "name": "opponent_threat",
        "description": "Estimate how close each opponent is to solving (shadow notebooks + exact solver): n_possible, p_win_next_turn, most_dangerous.",
        "parameters": {"type": "object", "properties": {}},
    },
    {"name": "holder_probabilities", "description": "Exact probability that each card is held by each player or is in the envelope.", "parameters": {"type": "object", "properties": {}}},
    {"name": "hard_deductions", "description": "Certain facts provable from the evidence (e.g. 'P3 must hold Lounge', 'Rope is in the envelope').", "parameters": {"type": "object", "properties": {}}},
]

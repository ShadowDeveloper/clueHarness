"""Coach mode: opt-in solver hints for a human seat. Shared by the TUI and the web UI.

Hints are computed from the viewer's *own* notebook only, never persisted, and every use is logged by the caller
(`gm.log_agent_note(..., "coach_mode_on")`) so replays show when a human had help.
"""

from __future__ import annotations

from typing import Any

from clue.manager.game_manager import GameManager
from clue.rules import Action


def coach_hints(gm: GameManager, pid: str, observation: dict[str, Any] | None = None, legal: list[Action] | None = None) -> dict[str, Any]:
    """Structured hints: candidate count, most likely envelope, hard deductions, and what the expert bot would do now."""
    from clue.agents.expert import BaselineExpertBot
    from clue.tools.solver import hard_deductions, solve

    obs = observation or gm.get_observation(pid)
    nb = gm.notebooks[pid]
    sizes = {p["id"]: p["hand_size"] for p in obs["board"]["players"]}
    sol = solve(nb, gm.player_ids(), sizes, obs["config"]["edition"])
    best, pb = sol.best
    out: dict[str, Any] = {
        "candidates": len(sol.combos),
        "most_likely": {"suspect": best[0], "weapon": best[1], "room": best[2], "p": round(pb, 4)} if best and len(sol.combos) > 1 else None,
        "deductions": list(hard_deductions(sol, nb)[:4]),
        "expert_action": None,
        "error": None,
    }
    if legal:
        try:
            o = dict(obs)
            o["_notebook_obj"] = nb
            act = BaselineExpertBot(pid, seed=0, gamble=False, exact_top=0).choose_action(o, legal)
            out["expert_action"] = {"key": act.key(), "action": act.model_dump(exclude_none=True)}
        except Exception as e:  # coach must never break the game loop
            out["error"] = str(e)
    return out

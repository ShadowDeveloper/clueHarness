"""opponent_threat: shadow-notebook modelling of rivals."""

from __future__ import annotations

from clue.agents.factory import make_agent, parse_players_arg
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game
from clue.tools.opponent import opponent_threat
from clue.tools.solver import solve


def _sizes(gm: GameManager) -> dict[str, int]:
    return {p.id: len(p.hand) for p in gm.state.players}


def test_threat_shape_and_bounds() -> None:
    specs = parse_players_arg("baseline,baseline,baseline")
    gm = GameManager.create(specs, seed=1)
    obs = gm.get_observation("P1")
    th = opponent_threat(gm.notebooks["P1"], gm.player_ids(), "P1", _sizes(gm), "classic", obs["public_history"])
    assert set(th["opponents"]) == {"P2", "P3"}
    for d in th["opponents"].values():
        assert d["n_possible"] >= 1 and 0.0 <= d["p_win_next_turn"] <= 1.0
    assert 0.0 <= th["p_any_wins_before_my_turn"] <= 1.0
    assert th["max_threat"] == 0.0  # nothing has happened yet


def test_threat_tracks_true_opponent_knowledge() -> None:
    """Estimated candidate counts must correlate with opponents' real solver counts and flag solved rivals."""
    specs = parse_players_arg("baseline,baseline,baseline,baseline")
    gm = GameManager.create(specs, seed=5)
    agents = {s.id: make_agent(s, seed=5) for s in specs}
    players = gm.player_ids()
    pairs: list[tuple[int, int]] = []
    tick = [0]

    def cb(g: GameManager, evs: list[dict[str, object]]) -> None:
        tick[0] += 1
        if tick[0] % 6:
            return
        obs = g.get_observation("P1")
        th = opponent_threat(g.notebooks["P1"], players, "P1", _sizes(g), "classic", obs["public_history"])
        for opp, d in th["opponents"].items():
            pairs.append((d["n_possible"], len(solve(g.notebooks[opp], players).combos)))

    run_game(gm, agents, on_events=cb)
    assert pairs
    solved = [est for est, true in pairs if true == 1]
    if solved:
        assert max(solved) <= 6
    # monotone-ish: estimates for rivals with many candidates exceed estimates for rivals with few
    many = [est for est, true in pairs if true > 50]
    few = [est for est, true in pairs if true <= 5]
    if many and few:
        assert sum(many) / len(many) > sum(few) / len(few)


def test_threat_never_leaks_private_cards() -> None:
    """The shadow notebook must be built only from the viewer's own notebook + public history."""
    specs = parse_players_arg("baseline,baseline,baseline")
    gm = GameManager.create(specs, seed=9)
    agents = {s.id: make_agent(s, seed=9) for s in specs}
    run_game(gm, agents)
    obs = gm.get_observation("P1")
    nb = gm.notebooks["P1"]
    th = opponent_threat(nb, gm.player_ids(), "P1", _sizes(gm), "classic", obs["public_history"])
    # sanity: history given to the tool contains no other player's private card reveals
    for ev in obs["public_history"]:
        if ev.get("type") == "disproved" and "card" in ev:
            assert "P1" in (ev.get("player"), ev.get("suggester"))
    assert "P1" not in th["opponents"]

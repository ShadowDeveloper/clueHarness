"""Large edition: 12 suspects / 12 weapons / 12 rooms, up to 12 players on the Hill House board."""

from __future__ import annotations

import hashlib
import json
import random

import pytest

from clue.agents.factory import make_agent
from clue.manager import PlayerSpec
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game
from clue.rules import GameConfig, new_game
from clue.rules import board as B
from clue.rules.cards import all_cards, category, edition_def, max_players, rooms, suspects
from clue.tools.solver import solve


def test_large_card_lists():
    ed = edition_def("large")
    assert len(ed.suspects) == 12 and len(ed.weapons) == 12 and len(ed.rooms) == 12
    assert len(all_cards("large")) == 36 and ed.n_dealt == 33
    assert suspects("large")[:6] == suspects("classic")
    for name in ("Wadsworth", "Yvette", "Miss Peach", "Sgt. Gray", "Mr. Boddy", "Madame Rose"):
        assert name in suspects("large")
    for room in ("Attic", "Cellar", "Garage", "Gazebo", "Courtyard", "Carriage House"):
        assert room in rooms("large")
    assert category("Poison", "large") == "weapon" and category("Gazebo", "large") == "room"
    with pytest.raises(ValueError):
        category("Poison", "classic")
    assert max_players("classic") == 6 and max_players("large") == 12


def test_large_board_geometry_is_consistent():
    board = B.board_for("large")
    assert set(board.rooms) == set(rooms("large"))
    assert len(board.starts) == 12
    for room in board.rooms:
        assert board.doors[room], room
    for a, b in board.passages.items():
        assert board.passages[b] == a
    geo = B.geometry("large")
    assert geo["rows"] == B.ROWS_LARGE and geo["cols"] == B.COLS_LARGE and geo["cellar"] == list(B.CENTRE_LARGE)
    # every room reachable from every start with a big enough roll budget
    for start in board.starts.values():
        pos = B.sq(*start)
        seen: set[str] = set()
        for steps in range(1, 80):
            seen |= {d for d in B.reachable(pos, steps, frozenset(), "large") if B.is_room(d)}
        assert seen == set(board.rooms), (start, set(board.rooms) - seen)
    txt = B.ascii_board({"Miss Scarlet": "35,8", "Wadsworth": "Cellar"}, {"Miss Scarlet": "S", "Wadsworth": "W"}, "large")
    assert "COURTY" in txt and "GAZEBO" in txt and "CELLAR" in txt and "S" in txt


def test_classic_board_unchanged():
    assert B.board_for("classic") is B.BOARD and B.board_for("modern") is B.BOARD
    assert B.reachable("24,7", 7, frozenset()) == B.reachable("24,7", 7, frozenset(), "classic")
    assert B.geometry()["rows"] == 25


def test_new_game_large_12_players():
    cfg = GameConfig(edition="large", num_players=12)
    st = new_game(cfg, [f"P{i}" for i in range(12)], random.Random(1))
    assert len(st.token_positions) == 12 and len(st.weapon_positions) == 12
    assert set(st.weapon_positions.values()) <= set(rooms("large"))
    dealt = sum(len(p.hand) for p in st.players)
    assert dealt == 33 and {len(p.hand) for p in st.players} <= {2, 3}
    assert category(st.solution[0], "large") == "suspect" and category(st.solution[1], "large") == "weapon"
    with pytest.raises(ValueError):
        new_game(GameConfig(edition="classic", num_players=7), [f"P{i}" for i in range(7)], random.Random(1))


def _play(bots: list[str], seed: int) -> GameManager:
    specs = [PlayerSpec(id=f"P{i + 1}", kind="baseline", bot=b) for i, b in enumerate(bots)]
    gm = GameManager.create(specs, seed=seed, config=GameConfig(edition="large", num_players=len(bots)))
    agents = {s.id: make_agent(s, i) for i, s in enumerate(specs)}
    run_game(gm, agents)
    return gm


def test_full_12_player_game_finishes_legally_and_is_deterministic():
    a = _play(["heuristic"] * 12, 3)
    assert a.finished and a.state.winner is not None
    assert not any(e.type == "illegal" for e in a.events)
    b = _play(["heuristic"] * 12, 3)
    ha = hashlib.sha256(json.dumps(a.export_replay(), sort_keys=True, default=str).encode()).hexdigest()
    hb = hashlib.sha256(json.dumps(b.export_replay(), sort_keys=True, default=str).encode()).hexdigest()
    assert ha == hb


def test_expert_plays_large_edition():
    gm = _play(["expert", "heuristic", "heuristic"], 8)
    assert gm.finished and gm.state.winner is not None
    # a wrong accusation eliminates; the expert must never accuse wrongly
    for e in gm.events:
        if e.type == "accuse" and e.player == "P1":
            assert e.public.get("correct") is True


def test_sampled_solver_is_sound_on_large_table():
    gm = _play(["heuristic"] * 12, 5)
    sol_truth = gm.state.solution
    for pid in gm.player_ids()[:4]:
        nb = gm.notebooks[pid]
        # rewind-free check: the final notebook must still admit the true solution
        s = solve(nb, gm.player_ids(), {p.id: len(p.hand) for p in gm.state.players}, "large")
        assert not s.exact
        assert sol_truth in s.combos
        for card, holder in s.certain_holder.items():
            if holder == "envelope":
                assert card in sol_truth
            else:
                assert card in gm.state.player(holder).hand

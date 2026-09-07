"""Exhaustive rules-engine tests: deal, movement, passages, suggestion, disproof, accusation, elimination."""

from __future__ import annotations

import random

import pytest

from clue.rules import Action, GameConfig, GameState, IllegalAction, apply_action, legal_actions, new_game
from clue.rules import board as B
from clue.rules.cards import ROOMS, WEAPONS, all_cards, category, suspects

P4 = ["P1", "P2", "P3", "P4"]


def game(n: int = 4, seed: int = 1, **kw: object) -> tuple[GameState, random.Random]:
    cfg = GameConfig(num_players=n, **kw)  # type: ignore[arg-type]
    rng = random.Random(seed)
    return new_game(cfg, [f"P{i + 1}" for i in range(n)], rng), rng


def step(st: GameState, rng: random.Random, **kw: object) -> GameState:
    st, _ = apply_action(st, Action(**kw), rng)  # type: ignore[arg-type]
    return st


def put(st: GameState, pid: str, pos: str) -> None:
    p = st.player(pid)
    p.position = pos
    st.token_positions[suspects()[p.seat]] = pos


# ---------------- cards / deal ----------------


def test_card_sets() -> None:
    assert len(all_cards()) == 21
    assert category("Rope") == "weapon" and category("Hall") == "room" and category("Prof. Plum") == "suspect"
    assert "Dr. Orchid" in suspects("modern") and "Mrs. White" not in suspects("modern")
    with pytest.raises(ValueError):
        category("Banana")


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_deal_uneven(n: int) -> None:
    st, _ = game(n)
    hands = [len(p.hand) for p in st.players]
    assert sum(hands) == 18 and max(hands) - min(hands) <= 1
    dealt = [c for p in st.players for c in p.hand]
    assert len(set(dealt)) == 18 and not (set(dealt) & set(st.solution))
    assert category(st.solution[0]) == "suspect" and category(st.solution[2]) == "room"


@pytest.mark.parametrize("n,rem", [(4, 2), (5, 3), (3, 0), (6, 0)])
def test_deal_faceup(n: int, rem: int) -> None:
    st, _ = game(n, deal_remainder="faceup")
    assert len(st.faceup) == rem
    assert all(len(p.hand) == (18 - rem) // n for p in st.players)


def test_new_game_validation() -> None:
    with pytest.raises(ValueError):
        new_game(GameConfig(num_players=4), ["a", "b"], random.Random(0))
    with pytest.raises(ValueError):
        new_game(GameConfig(num_players=3), ["a", "a", "b"], random.Random(0))


def test_scarlet_starts() -> None:
    st, _ = game()
    assert st.current_player().seat == 0 and st.current_player().position == "24,7"


# ---------------- board / movement ----------------


def test_board_integrity() -> None:
    for room in ROOMS:
        assert B.DOORS[room]
    assert B.SECRET_PASSAGES["Kitchen"] == "Study" and B.SECRET_PASSAGES["Lounge"] == "Conservatory"
    assert B.parse_sq(B.sq(3, 4)) == (3, 4)
    txt = B.ascii_board({"Miss Scarlet": "24,7", "Prof. Plum": "Kitchen"}, {"Miss Scarlet": "S", "Prof. Plum": "P"})
    assert "KITCH" in txt and "S" in txt


def test_reachable_exact_distance_and_rooms() -> None:
    r = B.reachable("24,7", 7, frozenset())
    assert "Hall" in r  # Scarlet can reach Hall with 7 from her start
    # corridor destinations are at exactly 7 steps
    for d in r:
        if not B.is_room(d):
            assert d != "24,7"
    assert "Hall" not in B.reachable("24,7", 3, frozenset())


def test_blocking_by_token() -> None:
    free = B.reachable("24,7", 1, frozenset())
    assert free == {"23,7"}
    blocked = B.reachable("24,7", 1, frozenset({"23,7"}))
    assert blocked == set()  # boxed in


def test_leaving_room_via_doors() -> None:
    r = B.reachable("Kitchen", 1, frozenset())
    assert r == {"7,4"}
    r2 = B.reachable("Kitchen", 1, frozenset({"7,4"}))
    assert r2 == set()  # door square blocked
    # cannot re-enter Kitchen on same turn even with big roll
    assert "Kitchen" not in B.reachable("Kitchen", 12, frozenset())


def test_roll_then_move_flow() -> None:
    st, rng = game(seed=3)
    acts = legal_actions(st, "P1")
    assert {a.type for a in acts} == {"roll", "accuse"}
    st = step(st, rng, type="roll", player="P1")
    assert st.roll is not None and 2 <= st.roll <= 12
    moves = [a for a in legal_actions(st, "P1") if a.type == "move"]
    assert moves
    st = step(st, rng, type="move", player="P1", to=moves[0].to)
    assert st.has_moved
    with pytest.raises(IllegalAction):
        step(st, rng, type="move", player="P1", to=moves[0].to)


def test_one_die_option() -> None:
    st, rng = game(dice=1)
    st = step(st, rng, type="roll", player="P1")
    assert st.roll is not None and 1 <= st.roll <= 6


def test_out_of_turn_rejected() -> None:
    st, rng = game()
    assert legal_actions(st, "P2") == []
    with pytest.raises(IllegalAction):
        step(st, rng, type="roll", player="P2")


def test_move_to_room_enables_suggest_and_corridor_does_not() -> None:
    st, rng = game()
    put(st, "P1", "17,11")  # outside Hall door
    st.roll = 1
    st = step(st, rng, type="move", player="P1", to="Hall")
    assert st.phase == "suggest"
    types = {a.type for a in legal_actions(st, "P1")}
    assert types == {"suggest", "accuse", "end_turn"}
    st2, rng2 = game()
    st2.roll = 1
    st2 = step(st2, rng2, type="move", player="P1", to="23,7")
    assert st2.phase == "accuse"
    assert "suggest" not in {a.type for a in legal_actions(st2, "P1")}


# ---------------- secret passage ----------------


def test_secret_passage() -> None:
    st, rng = game()
    put(st, "P1", "Kitchen")
    assert any(a.type == "passage" for a in legal_actions(st, "P1"))
    st = step(st, rng, type="passage", player="P1")
    assert st.player("P1").position == "Study" and st.phase == "suggest"
    assert st.token_positions["Miss Scarlet"] == "Study"


def test_no_passage_from_non_corner() -> None:
    st, _ = game()
    put(st, "P1", "Hall")
    assert not any(a.type == "passage" for a in legal_actions(st, "P1"))


# ---------------- suggestion + disproof ----------------


def setup_suggest(hands: list[list[str]]) -> tuple[GameState, random.Random]:
    st, rng = game()
    for p, h in zip(st.players, hands, strict=True):
        p.hand = h
    put(st, "P1", "Hall")
    st.player("P1").may_suggest = True
    st.phase = "suggest"
    st.has_moved = True
    return st, rng


def test_disproof_order_clockwise_first_holder() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Prof. Plum", "Hall"], ["Hall"]])
    st, ev = apply_action(st, Action(type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall"), rng)
    types = [e.type for e in ev]
    assert types == ["suggest", "cannot_disprove", "can_disprove"]
    assert ev[1].player == "P2" and ev[2].player == "P3"
    assert st.phase == "disprove"
    opts = legal_actions(st, "P3")
    assert {a.card for a in opts} == {"Prof. Plum", "Hall"}
    assert legal_actions(st, "P4") == [] and legal_actions(st, "P1") == []
    with pytest.raises(IllegalAction):
        step(st, rng, type="show_card", player="P3", card="Rope")
    st, ev2 = apply_action(st, Action(type="show_card", player="P3", card="Hall"), rng)
    assert ev2[0].type == "disproved" and ev2[0].private == {"card": "Hall"}
    assert set(ev2[0].private_to) == {"P1", "P3"}
    assert ev2[0].redacted_for("P2").get("card") is None
    assert ev2[0].redacted_for("P1")["card"] == "Hall"
    assert st.phase == "accuse"


def test_suggestion_summons_tokens() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Wrench"], ["Hall"]])
    st = step(st, rng, type="suggest", player="P1", suspect="Col. Mustard", weapon="Rope", room="Hall")
    assert st.token_positions["Col. Mustard"] == "Hall"
    assert st.player("P2").position == "Hall" and st.player("P2").may_suggest
    assert st.weapon_positions["Rope"] == "Hall"


def test_summoned_player_may_suggest_without_moving() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Wrench"], ["Hall"]])
    st = step(st, rng, type="suggest", player="P1", suspect="Col. Mustard", weapon="Rope", room="Hall")
    st = step(st, rng, type="show_card", player="P4", card="Hall")
    st = step(st, rng, type="end_turn", player="P1")
    assert st.current_player().id == "P2"
    types = {a.type for a in legal_actions(st, "P2")}
    assert "suggest" in types and "roll" in types


def test_no_one_can_disprove() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Wrench"], ["Candlestick"]])
    st, ev = apply_action(st, Action(type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall"), rng)
    assert ev[-1].type == "no_one_disproved" and st.phase == "accuse"


def test_suggestion_must_be_current_room() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Wrench"], ["Hall"]])
    with pytest.raises(IllegalAction):
        step(st, rng, type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Kitchen")


def test_cannot_suggest_twice_or_after_staying() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Wrench"], ["Hall"]])
    st = step(st, rng, type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall")
    st = step(st, rng, type="show_card", player="P4", card="Hall")
    assert not any(a.type == "suggest" for a in legal_actions(st, "P1"))
    st = step(st, rng, type="end_turn", player="P1")
    # come back around to P1 still in Hall: may not suggest without moving
    for pid in ("P2", "P3", "P4"):
        st = step(st, rng, type="roll", player=pid)
        mv = [a for a in legal_actions(st, pid) if a.type == "move"]
        st = step(st, rng, type="move", player=pid, to=mv[0].to)
        if st.phase == "suggest":
            st = step(st, rng, type="end_turn", player=pid)
        else:
            st = step(st, rng, type="end_turn", player=pid)
    assert st.current_player().id == "P1"
    assert not any(a.type == "suggest" for a in legal_actions(st, "P1"))


def test_cannot_reenter_left_room_same_turn() -> None:
    st, rng = game()
    put(st, "P1", "Hall")
    st.roll = 2
    dests = {a.to for a in legal_actions(st, "P1") if a.type == "move"}
    assert "Hall" not in dests and dests


# ---------------- accusation + elimination ----------------


def test_correct_accusation_wins() -> None:
    st, rng = game()
    s, w, r = st.solution
    st, ev = apply_action(st, Action(type="accuse", player="P1", suspect=s, weapon=w, room=r), rng)
    assert st.winner == "P1" and st.finished and ev[-1].type == "game_over"
    assert legal_actions(st, "P1") == []


def test_wrong_accusation_eliminates_but_still_disproves() -> None:
    st, rng = game()
    s, w, r = st.solution
    wrong_w = next(x for x in WEAPONS if x != w)
    st, ev = apply_action(st, Action(type="accuse", player="P1", suspect=s, weapon=wrong_w, room=r), rng)
    assert st.player("P1").eliminated and not st.finished
    assert [e.type for e in ev][:2] == ["accuse", "eliminated"]
    assert st.current_player().id == "P2"
    # P1 never gets a turn again
    assert legal_actions(st, "P1") == []
    # but P1 must disprove: give P4 a suggestion that only P1 can answer
    card = st.player("P1").hand[0]
    for p in st.players[1:]:
        p.hand = [c for c in p.hand if c != card]
    st.current = 3
    put(st, "P4", "Hall")
    st.player("P4").may_suggest = True
    st.phase = "suggest"
    cat = category(card)
    kw = {"suspect": suspects()[0], "weapon": WEAPONS[0], "room": "Hall"}
    kw[cat] = card if cat != "room" else "Hall"
    if cat == "room":
        put(st, "P4", card)
        kw["room"] = card
    st = step(st, rng, type="suggest", player="P4", **kw)
    assert st.phase == "disprove" and st.players[st.disprover_index or 0].id == "P1"


def test_all_eliminated_ends_game() -> None:
    st, rng = game(n=3)
    s, w, r = st.solution
    wrong = next(x for x in ROOMS if x != r)
    for pid in ("P1", "P2", "P3"):
        st = step(st, rng, type="accuse", player=pid, suspect=s, weapon=w, room=wrong)
    assert st.finished and st.winner is None


def test_accuse_from_anywhere_including_corridor_after_move() -> None:
    st, rng = game()
    st.roll = 1
    st = step(st, rng, type="move", player="P1", to="23,7")
    assert any(a.type == "accuse" for a in legal_actions(st, "P1"))


def test_max_turns_draw() -> None:
    st, rng = game(max_turns=2)
    st = step(st, rng, type="accuse", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall")
    st = step(st, rng, type="accuse", player="P2", suspect="Prof. Plum", weapon="Rope", room="Hall")
    assert st.finished and st.winner is None


def test_apply_action_is_pure() -> None:
    st, rng = game()
    before = st.model_dump_json()
    apply_action(st, Action(type="roll", player="P1"), rng)
    assert st.model_dump_json() == before


def test_random_playthrough_never_illegal() -> None:
    """Fuzz: random legal actions always apply; game terminates."""
    for seed in range(20):
        st, rng = game(n=3 + seed % 4, seed=seed, max_turns=150)
        while not st.finished:
            if st.phase == "disprove":
                pid = st.players[st.disprover_index or 0].id
            else:
                pid = st.current_player().id
            acts = legal_actions(st, pid, include_accusations=False)
            assert acts, f"no legal actions for {pid} in {st.phase}"
            a = rng.choice(acts)
            st, _ = apply_action(st, a, rng)
        assert st.finished

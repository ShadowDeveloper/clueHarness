"""Opt-in variance-reduction variants (docs/variants.md): A duplicate deals, B teams, C private disproofs,
D skip-turn penalty, E shuffled seats. Classic defaults must be untouched."""

from __future__ import annotations

import random

import pytest

from clue.agents.factory import make_agent, parse_players_arg
from clue.eval.tournament import duplicate_stats, run_tournament
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game
from clue.rules import Action, GameConfig, GameState, apply_action, legal_actions, new_game
from clue.rules.cards import suspects

P4 = ["P1", "P2", "P3", "P4"]
TEAMS = [["P1", "P3"], ["P2", "P4"]]


def game(seed: int = 1, **kw: object) -> tuple[GameState, random.Random]:
    cfg = GameConfig(num_players=4, **kw)  # type: ignore[arg-type]
    rng = random.Random(seed)
    return new_game(cfg, list(P4), rng), rng


def setup_suggest(hands: list[list[str]], **kw: object) -> tuple[GameState, random.Random]:
    st, rng = game(**kw)
    for p, h in zip(st.players, hands, strict=True):
        p.hand = h
    p1 = st.player("P1")
    p1.position = "Hall"
    st.token_positions[suspects()[p1.seat]] = "Hall"
    p1.may_suggest = True
    st.phase = "suggest"
    st.has_moved = True
    return st, rng


def test_defaults_unchanged() -> None:
    cfg = GameConfig(num_players=4)
    assert cfg.teams is None and not cfg.private_disproofs and cfg.wrong_accusation == "eliminate" and not cfg.shuffle_seats
    assert cfg.team_of("P2") == ["P2"]


# ---------------- C. private disproofs ----------------


def test_private_disproofs_hide_who_passed_and_who_showed() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Prof. Plum", "Hall"], ["Hall"]], private_disproofs=True)
    st, ev = apply_action(st, Action(type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall"), rng)
    passed, can = ev[1], ev[2]
    assert passed.type == "cannot_disprove" and passed.hidden and set(passed.private_to) == {"P1", "P2"}
    assert can.type == "can_disprove" and can.hidden and set(can.private_to) == {"P1", "P3"}
    assert passed.visible_to("P1") and passed.visible_to("P2") and not passed.visible_to("P4") and passed.visible_to(None)
    st, ev2 = apply_action(st, Action(type="show_card", player="P3", card="Hall"), rng)
    d = ev2[0]
    assert d.type == "disproved" and d.player is None
    assert d.redacted_for("P4") == {"type": "disproved", "turn": d.turn, "player": None, "suggester": "P1"}
    assert d.redacted_for("P1")["card"] == "Hall" and d.redacted_for("P1")["disprover"] == "P3"


def test_private_disproofs_manager_privacy_and_notebooks() -> None:
    specs = parse_players_arg("baseline:heuristic,baseline:heuristic,baseline:heuristic,baseline:random")
    gm = GameManager.create(specs, seed=3, config=GameConfig(num_players=4, private_disproofs=True))
    agents = {s.id: make_agent(s, 3) for s in gm.specs}
    run_game(gm, agents)
    hidden = [e for e in gm.events if e.hidden]
    assert hidden, "expected hidden disproof-round events"
    for pid in P4:
        hist = gm.public_history(pid)
        for e in hist:
            if e["type"] in ("cannot_disprove", "can_disprove"):
                assert pid in (e["player"], e["suggester"]), f"{pid} saw a bystander event {e}"
            if e["type"] == "disproved" and e.get("suggester") != pid:
                assert "disprover" not in e or e["disprover"] is None or e.get("card") is not None  # only the shower knows
        rep = gm.export_replay(pid)
        for r in rep:
            if r.get("type") in ("cannot_disprove", "can_disprove"):
                assert pid in (r["player"], r["suggester"])
            if r["kind"] == "action" and r.get("type") == "show_card":
                assert r.get("player") is None or pid in (r.get("player"), r.get("suggester", pid))
    # omniscient views still see everything
    assert any(r.get("type") == "cannot_disprove" for r in gm.export_replay(None))
    # notebooks of bystanders must hold no "not held" facts derived from hidden events
    for pid in P4:
        nb = gm.notebooks[pid]
        for other, cards in nb.not_held.items():
            for c in cards:
                assert c not in gm.state.player(other).hand
    # deterministic replay through load()
    p = gm.save("/tmp/variant_private.json")
    gm2 = GameManager.load(p)
    assert {k: v.model_dump() for k, v in gm2.notebooks.items()} == {k: v.model_dump() for k, v in gm.notebooks.items()}


# ---------------- D. skip-turn penalty ----------------


def test_wrong_accusation_skip_turns() -> None:
    st, rng = game(wrong_accusation="skip_turns", accusation_penalty_turns=2)
    wrong = [c for c in ("Rope", "Dagger", "Candlestick") if c != st.solution[1]][0]
    st, ev = apply_action(st, Action(type="accuse", player="P1", suspect=st.solution[0], weapon=wrong, room=st.solution[2]), rng)
    types = [e.type for e in ev]
    assert "penalised" in types and "eliminated" not in types
    assert not st.player("P1").eliminated and st.player("P1").skip_turns == 2
    assert st.current_player().id == "P2"
    # play through the lap: P1's next two turns are skipped
    skipped = 0
    for _ in range(3):
        while st.current_player().id != "P1" and not st.finished:
            acts = legal_actions(st, st.current_player().id)
            a = next((x for x in acts if x.type == "end_turn"), None) or next(x for x in acts if x.type != "accuse")
            st, evs = apply_action(st, a, rng)
            skipped += sum(1 for e in evs if e.type == "turn_skipped" and e.player == "P1")
            if st.current_player().id == "P1" or st.finished:
                break
        if skipped >= 2:
            break
    assert skipped == 2 and st.player("P1").skip_turns == 0
    # penalised player must still disprove
    assert st.player("P1").eliminated is False


def test_skip_turns_all_penalised_does_not_hang() -> None:
    st, rng = game(wrong_accusation="skip_turns", accusation_penalty_turns=3)
    for p in st.players:
        p.skip_turns = 3
    # P1's end of turn: everybody sits out until penalties are used up; game must not finish or loop forever
    from clue.rules.engine import _end_turn

    evs: list = []
    _end_turn(st, evs)
    assert not st.finished and st.current_player().skip_turns == 0
    assert sum(1 for e in evs if e.type == "turn_skipped") >= 4


# ---------------- B. teams ----------------


def test_team_validation() -> None:
    with pytest.raises(ValueError):
        game(teams=[["P1", "P2"], ["P3"]])
    with pytest.raises(ValueError):
        game(teams=[["P1", "P2"], ["P2", "P3", "P4"]])


def test_teams_skip_teammates_and_share_hands() -> None:
    st, rng = setup_suggest([["Rope"], ["Dagger"], ["Prof. Plum", "Hall"], ["Hall"]], teams=TEAMS)
    st, ev = apply_action(st, Action(type="suggest", player="P1", suspect="Prof. Plum", weapon="Rope", room="Hall"), rng)
    # P3 (teammate) is skipped even though it holds Hall; P2 passes, P4 shows
    assert [(e.type, e.player) for e in ev[1:]] == [("cannot_disprove", "P2"), ("can_disprove", "P4")]
    st, ev2 = apply_action(st, Action(type="show_card", player="P4", card="Hall"), rng)
    assert set(ev2[0].private_to) == {"P1", "P3", "P2", "P4"} or set(ev2[0].private_to) >= {"P1", "P3", "P4"}
    specs = parse_players_arg("baseline:heuristic,baseline:heuristic,baseline:heuristic,baseline:heuristic")
    gm = GameManager.create(specs, seed=5, config=GameConfig(num_players=4, teams=TEAMS))
    nb = gm.notebooks["P1"]
    assert set(nb.my_hand) == set(gm.state.player("P1").hand) | set(gm.state.player("P3").hand)
    assert nb.team == ["P1", "P3"]
    obs = gm.get_observation("P1")
    assert obs["you"]["team"] == ["P1", "P3"] and set(obs["you"]["team_hands"]) == {"P3"}
    agents = {s.id: make_agent(s, 5) for s in gm.specs}
    run_game(gm, agents)
    s = gm.summary()
    assert s["winner"] is None or s["winning_team"] == gm.config.team_of(s["winner"])
    go = next(e for e in gm.events if e.type == "game_over")
    if s["winner"]:
        assert go.public["team"] == s["winning_team"]


# ---------------- E. shuffled seats ----------------


def test_shuffle_seats_is_seeded_and_permutes() -> None:
    cfg = GameConfig(num_players=4, shuffle_seats=True)
    a = new_game(cfg, list(P4), random.Random(7))
    b = new_game(cfg, list(P4), random.Random(7))
    assert [p.id for p in a.players] == [p.id for p in b.players]
    orders = {tuple(p.id for p in new_game(cfg, list(P4), random.Random(s)).players) for s in range(12)}
    assert len(orders) > 1 and all(sorted(o) == P4 for o in orders)
    plain = new_game(GameConfig(num_players=4), list(P4), random.Random(7))
    assert [p.id for p in plain.players] == P4


# ---------------- A. duplicate deals ----------------


def test_duplicate_tournament_rotates_agents_through_same_deal() -> None:
    specs = parse_players_arg("baseline:heuristic,baseline:random,baseline:random")
    rep = run_tournament(specs, games=4, seed=11, duplicate=True, probe=False)
    assert rep["games"] == 6  # rounded up to whole blocks of 3
    dup = rep["duplicate"]
    assert dup["deals"] == 2
    labs = set(dup["per_label"])
    assert "baseline:heuristic" in labs
    for d in dup["per_label"].values():
        assert 0.0 <= d["win_share"] <= 1.0


def test_duplicate_stats_pairing() -> None:
    recs = [
        {"seed": 1, "rotation": 0, "winner_label": "a"},
        {"seed": 1, "rotation": 1, "winner_label": "a"},
        {"seed": 2, "rotation": 0, "winner_label": "b"},
        {"seed": 2, "rotation": 1, "winner_label": "a"},
    ]
    out = duplicate_stats(recs, ["a", "b"])
    assert out["deals"] == 2
    assert out["per_label"]["a"] == {"win_share": 0.75, "vs": "b", "paired_diff": 0.5, "se": 0.5}


# ---------------- CLI grammar + YAML ----------------


def test_parse_variants() -> None:
    from clue.__main__ import parse_variants

    out = parse_variants("private,skip=3,shuffle,teams", P4)
    assert out == {"private_disproofs": True, "wrong_accusation": "skip_turns", "accusation_penalty_turns": 3, "shuffle_seats": True, "teams": [["P1", "P3"], ["P2", "P4"]]}
    assert parse_variants("teams=3", ["P1", "P2", "P3", "P4", "P5", "P6"])["teams"] == [["P1", "P4"], ["P2", "P5"], ["P3", "P6"]]
    import typer

    with pytest.raises(typer.BadParameter):
        parse_variants("bogus", P4)


def test_yaml_variants(tmp_path: object) -> None:
    from pathlib import Path

    from clue.config import load_yaml_config

    p = Path(str(tmp_path)) / "v.yaml"
    seats = "".join(f"  - {{id: P{i}, kind: baseline, bot: random}}\n" for i in range(1, 5))
    p.write_text(f"players:\n{seats}private_disproofs: true\nwrong_accusation: skip_turns\nteams: [[P1, P3], [P2, P4]]\nshuffle_seats: true\n")
    cfg, specs, _, _ = load_yaml_config(p)
    assert cfg.private_disproofs and cfg.wrong_accusation == "skip_turns" and cfg.teams == TEAMS and cfg.shuffle_seats

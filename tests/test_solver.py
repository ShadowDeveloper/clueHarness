"""Exact solver: brute-force equivalence, soundness on real games, hard deductions, tool wrappers."""

from __future__ import annotations

import itertools
import random

from clue.agents.baselines import BaselineHeuristicBot
from clue.manager import GameManager, PlayerSpec
from clue.manager.notebook import Constraint, Notebook
from clue.manager.runner import run_game
from clue.rules.cards import ROOMS, WEAPONS, suspects
from clue.tools import get_possible_solutions, hard_deductions, holder_probabilities, solution_probabilities, solve


def brute(nb: Notebook, players: list[str], sizes: dict[str, int]) -> tuple[dict[tuple[str, str, str], int], dict[str, dict[str, int]]]:
    sus = list(suspects())
    allc = sus + list(WEAPONS) + list(ROOMS)
    known = nb.known_holder
    pool = [c for c in allc if c not in known and c not in nb.faceup]
    combos: dict[tuple[str, str, str], int] = {}
    holder: dict[str, dict[str, int]] = {c: {} for c in pool}
    caps = {p: sizes[p] - sum(1 for c, h in known.items() if h == p) for p in players}
    for env in itertools.product([c for c in sus if c not in known], [c for c in WEAPONS if c not in known], [c for c in ROOMS if c not in known]):
        rem = [c for c in pool if c not in env]

        def rec(i: int, hands: dict[str, set[str]], rem: list[str] = rem) -> int:
            if i == len(rem):
                full = {p: hands[p] | {c for c, h in known.items() if h == p} for p in players}
                for p in players:
                    if set(nb.not_held.get(p, [])) & full[p]:
                        return 0
                for con in nb.has_one_of:
                    if not (set(con.cards) & full[con.player]):
                        return 0
                for p in players:
                    for x in hands[p]:
                        holder[x][p] = holder[x].get(p, 0) + 1
                return 1
            n = 0
            for p in players:
                if len(hands[p]) < caps[p]:
                    hands[p].add(rem[i])
                    n += rec(i + 1, hands, rem)
                    hands[p].discard(rem[i])
            return n

        n = rec(0, {p: set() for p in players})
        if n:
            combos[env] = n
    return combos, holder


def random_case(rng: random.Random, nplayers: int, reveal: int, ncons: int) -> tuple[Notebook, list[str], dict[str, int], tuple[str, str, str]]:
    sus = list(suspects())
    allc = sus + list(WEAPONS) + list(ROOMS)
    players = [chr(65 + i) for i in range(nplayers)]
    sol = (rng.choice(sus), rng.choice(WEAPONS), rng.choice(ROOMS))
    deck = [c for c in allc if c not in sol]
    rng.shuffle(deck)
    hands = {p: set(deck[i::nplayers]) for i, p in enumerate(players)}
    sizes = {p: len(hands[p]) for p in players}
    nb = Notebook(viewer="A", my_hand=sorted(hands["A"]))
    for c in hands["A"]:
        nb.known_holder[c] = "A"
    for p in players[1:]:
        for c in sorted(hands[p])[:reveal]:
            nb.known_holder[c] = p
    for _ in range(ncons):
        p = rng.choice(players[1:])
        t = [rng.choice(sus), rng.choice(WEAPONS), rng.choice(ROOMS)]
        if set(t) & hands[p]:
            nb.has_one_of.append(Constraint(player=p, cards=t, turn=0, suggester="A"))
        else:
            nb.mark_not_held(p, t)
    return nb, players, sizes, sol


def test_solver_matches_brute_force() -> None:
    rng = random.Random(7)
    for trial in range(10):
        nb, players, sizes, sol = random_case(rng, 3 if trial < 7 else 4, 2 + trial % 2, 4)
        s = solve(nb, players, sizes)
        bc, bh = brute(nb, players, sizes)
        assert dict(s.combos) == bc
        for c in bh:
            got = {k: round(v * s.n_assignments) for k, v in s.holder_probs[c].items() if k != "envelope"}
            assert bh[c] == got, c
        assert sol in s.combos


def test_solver_sound_on_full_games_and_solution_prob_sums() -> None:
    for seed in range(4):
        specs = [PlayerSpec(id=f"P{i}", kind="baseline") for i in range(1, 4 + seed % 3)]
        gm = GameManager.create(specs, seed=seed)
        run_game(gm, {p: BaselineHeuristicBot(p, i) for i, p in enumerate(gm.player_ids())})
        sizes = {p.id: len(p.hand) for p in gm.state.players}
        for nb in gm.notebooks.values():
            s = solve(nb, gm.player_ids(), sizes)
            assert tuple(gm.state.solution) in s.combos
            assert abs(sum(s.card_probs.values()) - 3.0) < 1e-9
            for card, probs in s.holder_probs.items():
                assert abs(sum(probs.values()) - 1.0) < 1e-9, card
            # certainties are true
            for card, holder in s.certain_holder.items():
                if holder == "envelope":
                    assert card in gm.state.solution
                elif holder != "faceup":
                    assert card in gm.state.player(holder).hand


def test_hard_deductions_and_wrappers() -> None:
    # Construct: 3 players, everything known except one card per category left for envelope
    sus = list(suspects())
    players = ["A", "B", "C"]
    nb = Notebook(viewer="A")
    env = ("Prof. Plum", "Rope", "Study")
    rest = [c for c in sus + list(WEAPONS) + list(ROOMS) if c not in env]
    for i, c in enumerate(rest):
        nb.known_holder[c] = players[i % 3]
    sizes = {p: sum(1 for h in nb.known_holder.values() if h == p) for p in players}
    assert get_possible_solutions(nb, players, sizes) == [env]
    post = solution_probabilities(nb, players, sizes)
    assert post["best"] == list(env) and post["best_prob"] == 1.0 and post["exact"]
    hd = hard_deductions(nb, players, sizes)
    assert any(h.startswith("SOLVED") for h in hd)
    assert "Rope is in the envelope" in hd
    hp = holder_probabilities(nb, players, sizes)
    assert hp["Rope"] == {"envelope": 1.0}


def test_forced_holder_deduction() -> None:
    """B disproved (Plum, Rope, Hall); A holds Plum and Rope -> B must hold Hall."""
    players = ["A", "B", "C"]
    nb = Notebook(viewer="A", my_hand=["Prof. Plum", "Rope", "Kitchen", "Dagger", "Mr. Green", "Lounge"])
    for c in nb.my_hand:
        nb.known_holder[c] = "A"
    nb.has_one_of.append(Constraint(player="B", cards=["Prof. Plum", "Rope", "Hall"], turn=1, suggester="A"))
    s = solve(nb, players, {"A": 6, "B": 6, "C": 6})
    assert s.certain_holder.get("Hall") == "B"
    assert "B must hold Hall" in hard_deductions(nb, players, {"A": 6, "B": 6, "C": 6})
    assert all(r != "Hall" for (_, _, r) in s.combos)

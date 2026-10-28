"""Opponent modelling: how close is each rival to solving the case?

We rebuild a *shadow notebook* for every opponent from information that is public (or that we personally
gave them) and run the edition-aware solver on it (exact within solver bounds, sampled otherwise). Because we
cannot see the cards shown to them by third parties,
we fill each such disproof with the card the shower most probably holds (from OUR posterior) — a
pessimistic-for-us estimate that, together with their hand, yields an upper-bound-ish knowledge state.

    opponent_threat(nb, players, me, hand_sizes, edition, history) ->
        {opponent: {"n_possible": int, "p_win_next_turn": float, "unrefuted": bool, "repeat_suggestion": bool,
                    "known_cards": int}}, plus "max_threat" and "most_dangerous".

`p_win_next_turn` is a heuristic: 1/n_possible when they have <= 6 candidates (they may gamble), 1.0 when
they have exactly one, boosted when they have just made an unrefuted suggestion or repeated a triple.
"""

from __future__ import annotations

from typing import Any

from clue.manager.notebook import Constraint, Notebook
from clue.tools.solver import Solution, solve


def _shadow_notebook(nb: Notebook, sol: Solution, me: str, opp: str, players: list[str], history: list[dict[str, Any]]) -> Notebook:
    hp = sol.holder_probs
    sh = Notebook(viewer=opp, faceup=list(nb.faceup))
    # cards we are (nearly) certain the opponent holds count as their hand knowledge
    for card, probs in hp.items():
        if probs.get(opp, 0.0) >= 0.999:
            sh.my_hand.append(card)
            sh.known_holder[card] = opp
    pending: dict[int, list[str]] = {}
    for ev in history:
        t, turn = ev.get("type"), int(ev.get("turn", 0))
        who = str(ev.get("player"))
        if t == "suggest":
            pending[turn] = [str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])]
            sh.suggestions_made[who] = sh.suggestions_made.get(who, 0) + 1
        elif t == "cannot_disprove":
            if turn in pending:
                sh.mark_not_held(who, pending[turn])
        elif t == "disproved":
            cards = pending.get(turn, [])
            who = str(ev.get("disprover") or ev.get("player"))
            if not cards or who == "None":  # private_disproofs: bystanders don't learn who showed
                continue
            suggester = str(ev.get("suggester"))
            if who == opp:
                continue  # they showed a card: tells them nothing new
            if suggester == opp:
                # they saw a specific card. If we showed it we know which; else guess the most likely one.
                if "card" in ev and who == me:
                    sh.known_holder[str(ev["card"])] = who
                else:
                    best = max(cards, key=lambda c: hp.get(c, {}).get(who, 0.0))
                    if hp.get(best, {}).get(who, 0.0) > 0:
                        sh.known_holder[best] = who
                    else:
                        sh.has_one_of.append(Constraint(player=who, cards=cards, turn=turn, suggester=suggester))
            else:
                sh.has_one_of.append(Constraint(player=who, cards=cards, turn=turn, suggester=suggester))
        elif t == "no_one_disproved":
            cards = [str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])]
            sh.unrefuted_suggestions.append(Constraint(player=who, cards=cards, turn=turn, suggester=who))
            for p in players:
                if p != who:
                    sh.mark_not_held(p, cards)
    return sh


def opponent_threat(
    nb: Notebook,
    players: list[str],
    me: str,
    hand_sizes: dict[str, int] | None,
    edition: str,
    history: list[dict[str, Any]],
    eliminated: set[str] | None = None,
    sol: Solution | None = None,
) -> dict[str, Any]:
    sol = sol or solve(nb, players, hand_sizes, edition)
    eliminated = eliminated or set()
    out: dict[str, Any] = {"opponents": {}}
    # recent suggestion triples per player for repeat detection
    triples: dict[str, list[tuple[str, str, str]]] = {}
    for ev in history:
        if ev.get("type") == "suggest":
            triples.setdefault(str(ev.get("player")), []).append((str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])))
    unrefuted_by = {str(c.player) for c in nb.unrefuted_suggestions[-len(players) :]}
    best_p = 0.0
    worst = None
    for opp in players:
        if opp == me or opp in eliminated:
            continue
        sh = _shadow_notebook(nb, sol, me, opp, players, history)
        ssol = solve(sh, players, hand_sizes, edition)
        # the opponent also knows the rest of their own hand, which we do not: discount by unknown-hand share
        n = max(1, len(ssol.combos))
        # cards in their hand we could not place remove roughly that many candidates from each category
        sizes = hand_sizes or {}
        unknown_hand = max(0, sizes.get(opp, 0) - len(sh.my_hand))
        n_est = max(1, int(round(n * (0.75**unknown_hand))))
        seq = triples.get(opp, [])
        repeat = len(seq) >= 2 and seq[-1] == seq[-2]
        unref = opp in unrefuted_by
        # P(they accuse correctly next turn): certain at 1; at 2-3 a rational rival may gamble, weight by 1/n
        # times a gamble propensity; beyond that essentially nobody accuses.
        if n_est == 1:
            p = 1.0
        elif n_est <= 3:
            p = 0.5 / n_est
        else:
            p = 0.0
        if unref:
            p = max(p, 0.5)
        if repeat:
            p = max(p, 0.35)
        out["opponents"][opp] = {"n_possible": n_est, "p_win_next_turn": round(p, 3), "unrefuted": unref, "repeat_suggestion": repeat, "known_cards": len(sh.known_holder)}
        if p > best_p:
            best_p, worst = p, opp
    out["max_threat"] = round(best_p, 3)
    out["most_dangerous"] = worst
    # probability at least one opponent wins before our next turn (independence approx.)
    q = 1.0
    for d in out["opponents"].values():
        q *= 1.0 - float(d["p_win_next_turn"])
    out["p_any_wins_before_my_turn"] = round(1.0 - q, 3)
    return out

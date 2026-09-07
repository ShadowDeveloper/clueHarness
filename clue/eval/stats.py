"""Evaluation statistics: Wilson intervals, paired-seed comparisons, candidate-count curves, agent fingerprints."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def paired_comparison(results: list[dict[str, Any]], a: str, b: str) -> dict[str, Any]:
    """Compare two labels across the *same seeds*: games where exactly one of them won.

    Returns a sign-test p-value (two-sided, exact binomial) on the discordant games.
    """
    a_only = b_only = 0
    for r in results:
        w = r.get("winner_label")
        if w == a:
            a_only += 1
        elif w == b:
            b_only += 1
    n = a_only + b_only
    if n == 0:
        return {"a": a, "b": b, "a_wins": 0, "b_wins": 0, "p_value": 1.0}
    k = min(a_only, b_only)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n * 2
    return {"a": a, "b": b, "a_wins": a_only, "b_wins": b_only, "p_value": round(min(1.0, p), 4)}


def candidate_curve(curves: dict[str, list[list[int]]]) -> dict[str, list[float]]:
    """Mean number of remaining candidate combos per own-turn index, per label (curves: label -> per-game lists)."""
    out: dict[str, list[float]] = {}
    for lab, games in curves.items():
        longest = max((len(g) for g in games), default=0)
        means = []
        for i in range(longest):
            vals = [g[i] for g in games if i < len(g)]
            means.append(round(statistics.mean(vals), 1) if vals else float("nan"))
        out[lab] = means
    return out


def fingerprint(per_game: list[dict[str, Any]]) -> dict[str, Any]:
    """Behavioural fingerprint from per-game agent stats dicts (as emitted by tournament)."""
    if not per_game:
        return {}
    keys = ["suggestions", "turns_alive", "turn_solved", "turn_accused", "passages", "rooms_visited", "cards_shown_distinct", "own_cards_in_suggestions"]
    fp: dict[str, Any] = {}
    for k in keys:
        vals = [g[k] for g in per_game if g.get(k) is not None]
        if vals:
            fp[k + "_mean"] = round(statistics.mean(vals), 2)
    solved = [g["turn_solved"] for g in per_game if g.get("turn_solved") is not None]
    fp["solved_rate"] = round(len(solved) / len(per_game), 3)
    acc = [g for g in per_game if g.get("turn_accused") is not None]
    prem = [g for g in acc if (g.get("n_at_accusation") or 1) > 1]
    fp["accusation_rate"] = round(len(acc) / len(per_game), 3)
    fp["premature_accusation_rate"] = round(len(prem) / len(per_game), 3)
    return fp


def summarise(results: list[dict[str, Any]], table: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach Wilson CIs to a tournament table and all pairwise paired comparisons."""
    for row in table:
        lo, hi = wilson(row["wins"], row["games"])
        row["win_ci95"] = [round(lo, 3), round(hi, 3)]
    labels = [r["agent"] for r in table]
    pairs = []
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            pairs.append(paired_comparison(results, a, b))
    return {"pairwise": pairs}


def group_curves(results: list[dict[str, Any]]) -> dict[str, list[list[int]]]:
    curves: dict[str, list[list[int]]] = defaultdict(list)
    for r in results:
        for lab, c in (r.get("curves") or {}).items():
            curves[lab].append(c)
    return dict(curves)

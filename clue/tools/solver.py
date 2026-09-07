"""Exact deduction solver for Clue.

Model: the 21 cards minus face-up cards are partitioned into the envelope (exactly one suspect, one
weapon, one room) and the players' hands (known sizes). Constraints from the notebook:
  * known_holder[card] = player            (card is in that hand)
  * not_held[player] ⊇ cards               (player lacks them)
  * has_one_of: player holds ≥1 of a triple (they disproved a suggestion)
We count, exactly, the number of complete assignments consistent with all constraints, per envelope
combo. Cards that are "free" (no constraint mentions them) are never branched on individually: their
placements are counted combinatorially, which keeps enumeration tiny in practice.

Public API
  solve(nb, players, hand_sizes, edition) -> Solution
    .combos: dict[(s,w,r) -> count]        exact weight of each consistent envelope
    .card_probs: dict[card -> P(in envelope)]
    .holder_probs: dict[card -> dict[player -> P]]  (players + "envelope")
    .certain_holder: dict[card -> player|"envelope"]  cards whose location is forced
    .n_assignments: total count
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from functools import cache, lru_cache
from math import comb

from clue.manager.notebook import Notebook
from clue.rules.cards import ROOMS, WEAPONS, suspects

Combo = tuple[str, str, str]
ENVELOPE = "envelope"


@dataclass
class Solution:
    combos: dict[Combo, int] = field(default_factory=dict)
    card_probs: dict[str, float] = field(default_factory=dict)
    holder_probs: dict[str, dict[str, float]] = field(default_factory=dict)
    certain_holder: dict[str, str] = field(default_factory=dict)
    n_assignments: int = 0

    @property
    def possible(self) -> list[Combo]:
        return sorted(self.combos)

    @property
    def best(self) -> tuple[Combo | None, float]:
        if not self.combos:
            return None, 0.0
        c = max(self.combos, key=lambda k: self.combos[k])
        return c, self.combos[c] / self.n_assignments


def _hand_sizes(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None) -> dict[str, int]:
    if hand_sizes:
        return hand_sizes
    base, rem = divmod(18 - len(nb.faceup), len(players))
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(players)}


def solve(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> Solution:
    sizes = _hand_sizes(nb, players, hand_sizes)
    sus = list(suspects(edition))  # type: ignore[arg-type]
    all_cards = sus + list(WEAPONS) + list(ROOMS)
    faceup = set(nb.faceup)
    known = dict(nb.known_holder)  # card -> player
    not_held = {p: set(nb.not_held.get(p, [])) for p in players}
    # constraint triples per player (dedupe)
    triples: dict[str, list[frozenset[str]]] = {p: [] for p in players}
    for con in nb.has_one_of:
        if con.player in triples:
            fs = frozenset(con.cards)
            if fs not in triples[con.player]:
                triples[con.player].append(fs)
    # Cards that are constrained (mentioned by any triple or known) vs free per category
    mentioned: set[str] = set(known)
    for ts in triples.values():
        for t in ts:
            mentioned |= t
    for p in players:
        mentioned |= not_held[p]  # not_held affects who may take a card -> treat as constrained

    cand_env = {
        "suspect": [c for c in sus if c not in known and c not in faceup],
        "weapon": [c for c in WEAPONS if c not in known and c not in faceup],
        "room": [c for c in ROOMS if c not in known and c not in faceup],
    }
    sol = Solution()
    # per-player remaining capacity after known cards
    base_cap = {p: sizes[p] - sum(1 for c, h in known.items() if h == p) for p in players}
    if any(v < 0 for v in base_cap.values()):
        return sol
    pool = [c for c in all_cards if c not in known and c not in faceup]
    holder_counts: dict[str, dict[str, int]] = {c: {p: 0 for p in players} | {ENVELOPE: 0} for c in pool}
    total = 0
    for env in itertools.product(cand_env["suspect"], cand_env["weapon"], cand_env["room"]):
        env_set = set(env)
        # quick reject: a triple whose cards are all in the envelope / not_held is unsatisfiable
        remaining = [c for c in pool if c not in env_set]
        constrained = [c for c in remaining if c in mentioned]
        free_count = len(remaining) - len(constrained)
        # triples already satisfied by known cards can be dropped; the rest must be met from `constrained`
        eff_triples = []
        for p in players:
            mine = {c for c, h in known.items() if h == p}
            eff_triples.append(tuple(t for t in triples[p] if not (t & mine)))
        count, per_card = _count_assignments(tuple(players), tuple(constrained), free_count, tuple(base_cap[p] for p in players), tuple(frozenset(not_held[p]) for p in players), tuple(eff_triples))
        if count == 0:
            continue
        sol.combos[env] = count
        total += count
        for c in env:
            holder_counts[c][ENVELOPE] += count
        for ci, c in enumerate(constrained):
            for pi, p in enumerate(players):
                holder_counts[c][p] += per_card[ci][pi]
        # free cards: uniformly distributed over remaining capacity
        if free_count:
            free = [c for c in remaining if c not in mentioned]
            # expected share for player p = (cap_p - constrained cards assigned to p) / free_count, averaged;
            # per_card totals give exactly the constrained load per player summed over assignments
            for pi, p in enumerate(players):
                load = sum(per_card[ci][pi] for ci in range(len(constrained)))  # sum over assignments of #constrained cards p got
                share = base_cap[p] * count - load  # sum over assignments of #free cards p got
                for c in free:
                    holder_counts[c][p] += share // free_count if free_count else 0
    sol.n_assignments = total
    if total == 0:
        return sol
    for env, cnt in sol.combos.items():
        for c in env:
            sol.card_probs[c] = sol.card_probs.get(c, 0.0) + cnt / total
    for c in all_cards:
        if c in known:
            sol.holder_probs[c] = {known[c]: 1.0}
            sol.certain_holder[c] = known[c]
        elif c in faceup:
            sol.holder_probs[c] = {"faceup": 1.0}
        else:
            probs = {h: n / total for h, n in holder_counts[c].items() if n}
            sol.holder_probs[c] = probs
            if len(probs) == 1:
                sol.certain_holder[c] = next(iter(probs))
    for c in all_cards:
        sol.card_probs.setdefault(c, 0.0)
    return sol


@lru_cache(maxsize=50_000)
def _count_assignments(
    players: tuple[str, ...],
    constrained: tuple[str, ...],
    free_count: int,
    caps: tuple[int, ...],
    not_held: tuple[frozenset[str], ...],
    triples: tuple[tuple[frozenset[str], ...], ...],
) -> tuple[int, tuple[tuple[int, ...], ...]]:
    """Count assignments of `constrained` cards to players (respecting caps/not_held/triples), with the
    `free_count` unconstrained cards filling the remaining capacity in multinomial ways.

    Returns (total, per_card[i][p] = number of assignments in which constrained card i is held by p).

    Algorithm: cards mentioned by some triple are assigned one by one in a DP whose state is
    (caps_left, unsatisfied triple indices per player) - many assignment paths collapse onto the same state.
    Cards constrained only by `not_held` are interchangeable within the same allowed-player mask and are
    distributed combinatorially at the leaves (`_tail_ways`). Marginals come from a forward pass over reachable
    states times the memoised backward counts.
    """
    n = len(players)
    if sum(caps) != len(constrained) + free_count:
        return 0, tuple(tuple(0 for _ in players) for _ in constrained)
    # per-player triple list (indices), and card -> list of (player, triple idx)
    trip_list: list[list[frozenset[str]]] = [list(t) for t in triples]
    in_triple: set[str] = set()
    for tl in trip_list:
        for t in tl:
            in_triple |= t
    head = [c for c in constrained if c in in_triple]
    tail = [c for c in constrained if c not in in_triple]

    # tail groups by allowed mask
    def mask_of(card: str) -> int:
        m = 0
        for pi in range(n):
            if card not in not_held[pi]:
                m |= 1 << pi
        return m

    tail_groups: dict[int, int] = {}
    for c in tail:
        tail_groups[mask_of(c)] = tail_groups.get(mask_of(c), 0) + 1
    groups = tuple(sorted(tail_groups.items()))
    full_mask = (1 << n) - 1

    @cache
    def tail_ways(caps_left: tuple[int, ...], groups_left: tuple[tuple[int, int], ...]) -> int:
        """Distribute grouped tail cards, then free cards, into caps_left."""
        if not groups_left:
            return _multinomial(list(caps_left)) if sum(caps_left) == free_count else 0
        (mask, k), rest = groups_left[0], groups_left[1:]
        allowed = [pi for pi in range(n) if mask >> pi & 1]
        total = 0

        def split(idx: int, left: int, cl: list[int], mult: int) -> None:
            nonlocal total
            if idx == len(allowed):
                if left == 0:
                    total += mult * tail_ways(tuple(cl), rest)
                return
            pi = allowed[idx]
            for take in range(min(left, cl[pi]) + 1):
                cl[pi] -= take
                split(idx + 1, left - take, cl, mult * comb(left, take))
                cl[pi] += take

        split(0, k, list(caps_left), 1)
        return total

    unsat0 = tuple(frozenset(range(len(tl))) for tl in trip_list)

    def step(i: int, caps_left: tuple[int, ...], unsat: tuple[frozenset[int], ...], pi: int) -> tuple[tuple[int, ...], tuple[frozenset[int], ...]] | None:
        card = head[i]
        if caps_left[pi] == 0 or card in not_held[pi]:
            return None
        cl = list(caps_left)
        cl[pi] -= 1
        new_unsat = list(unsat)
        if unsat[pi]:
            new_unsat[pi] = frozenset(ti for ti in unsat[pi] if card not in trip_list[pi][ti])
        # feasibility: every unsatisfied triple must still have an assignable card among head[i+1:]
        remaining = head[i + 1 :]
        for q in range(n):
            if new_unsat[q] and cl[q] == 0:
                return None
            for ti in new_unsat[q]:
                t = trip_list[q][ti]
                if not any((x in remaining) and (x not in not_held[q]) for x in t):
                    return None
        return tuple(cl), tuple(new_unsat)

    @cache
    def back(i: int, caps_left: tuple[int, ...], unsat: tuple[frozenset[int], ...]) -> int:
        if i == len(head):
            if any(unsat):
                return 0
            return tail_ways(caps_left, groups)
        total = 0
        for pi in range(n):
            nxt = step(i, caps_left, unsat, pi)
            if nxt is not None:
                total += back(i + 1, nxt[0], nxt[1])
        return total

    total = back(0, caps, unsat0)
    per: dict[str, list[int]] = {c: [0] * n for c in constrained}
    if total:
        # forward pass over head cards
        frontier: dict[tuple[tuple[int, ...], tuple[frozenset[int], ...]], int] = {(caps, unsat0): 1}
        for i in range(len(head)):
            nxt_frontier: dict[tuple[tuple[int, ...], tuple[frozenset[int], ...]], int] = {}
            for (cl, un), ways_in in frontier.items():
                for pi in range(n):
                    nxt = step(i, cl, un, pi)
                    if nxt is None:
                        continue
                    b = back(i + 1, nxt[0], nxt[1])
                    if b == 0:
                        continue
                    per[head[i]][pi] += ways_in * b
                    nxt_frontier[nxt] = nxt_frontier.get(nxt, 0) + ways_in
            frontier = nxt_frontier
        # tail marginals: for each terminal state, force one card of a group onto player p
        if tail:
            for (cl, un), ways_in in frontier.items():
                if any(un):
                    continue
                for gi, (mask, k) in enumerate(groups):
                    for pi in range(n):
                        if not (mask >> pi & 1) or cl[pi] == 0:
                            continue
                        g2 = list(groups)
                        g2[gi] = (mask, k - 1)
                        cl2 = list(cl)
                        cl2[pi] -= 1
                        w = tail_ways(tuple(cl2), tuple(g for g in g2 if g[1] > 0))
                        if w:
                            for c in tail:
                                if mask_of(c) == mask:
                                    per[c][pi] += ways_in * w
    per_card = tuple(tuple(per[c]) for c in constrained)
    _ = full_mask
    return total, per_card


def _multinomial(parts: list[int]) -> int:
    total = sum(parts)
    out = 1
    for k in parts:
        out *= comb(total, k)
        total -= k
    return out


def hard_deductions(sol: Solution, nb: Notebook) -> list[str]:
    """Human-readable certainties the solver can prove beyond what the notebook already states."""
    out = []
    for card, holder in sorted(sol.certain_holder.items()):
        if card in nb.known_holder or card in nb.faceup:
            continue
        out.append(f"{card} is in the envelope" if holder == ENVELOPE else f"{holder} must hold {card}")
    if len(sol.combos) == 1:
        s, w, r = next(iter(sol.combos))
        out.append(f"SOLVED: {s} / {w} / {r}")
    return out

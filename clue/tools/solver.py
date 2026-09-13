"""Exact deduction solver for Clue.

Model: the deck (21 cards classic, 36 large) minus face-up cards are partitioned into the envelope (exactly one suspect, one
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
import random
from dataclasses import dataclass, field
from functools import cache, lru_cache
from math import comb

from clue.manager.notebook import Notebook
from clue.rules.cards import edition_def, rooms, suspects, weapons

Combo = tuple[str, str, str]
ENVELOPE = "envelope"


@dataclass
class Solution:
    combos: dict[Combo, int] = field(default_factory=dict)
    card_probs: dict[str, float] = field(default_factory=dict)
    holder_probs: dict[str, dict[str, float]] = field(default_factory=dict)
    certain_holder: dict[str, str] = field(default_factory=dict)
    n_assignments: int = 0
    exact: bool = True  # False when produced by the sampled solver (big tables); certain_holder is still sound

    @property
    def possible(self) -> list[Combo]:
        return sorted(self.combos)

    @property
    def best(self) -> tuple[Combo | None, float]:
        if not self.combos:
            return None, 0.0
        c = max(self.combos, key=lambda k: self.combos[k])
        return c, self.combos[c] / self.n_assignments


def _hand_sizes(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None, edition: str = "classic") -> dict[str, int]:
    if hand_sizes:
        return hand_sizes
    base, rem = divmod(edition_def(edition).n_dealt - len(nb.faceup), len(players))
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(players)}


# Exact counting is used when the table is small enough; above this many players the DP state space
# (a tuple of remaining hand capacities) explodes, so we fall back to propagation + sampling.
EXACT_MAX_PLAYERS = 6
EXACT_MAX_HEAD = 22  # constrained cards handled by the DP
EXACT_MAX_CARDS = 21  # the classic deck; the 36-card large deck always uses the sampled solver
SAMPLES = 400
SAMPLE_TIME_BUDGET = 0.6  # seconds per sampled solve (deterministic given the evidence: sample count is fixed by a node budget, not wall time)
SAMPLE_NODE_BUDGET = 150_000  # total DFS nodes across all samples of one solve
_SAMPLED_CACHE: dict[tuple[object, ...], Solution] = {}


def solve(nb: Notebook, players: list[str], hand_sizes: dict[str, int] | None = None, edition: str = "classic") -> Solution:
    sizes = _hand_sizes(nb, players, hand_sizes, edition)
    sus = list(suspects(edition))
    all_cards = sus + list(weapons(edition)) + list(rooms(edition))
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
    head_n = len({c for ts in triples.values() for t in ts for c in t if c not in known})
    if len(players) > EXACT_MAX_PLAYERS or head_n > EXACT_MAX_HEAD or len(all_cards) > EXACT_MAX_CARDS:
        if not _propagate(players, sizes, known, not_held, triples, all_cards, faceup):
            return Solution()
        return _solve_sampled(players, sizes, known, not_held, triples, all_cards, faceup, edition)
    # Cards that are constrained (mentioned by any triple or known) vs free per category
    mentioned: set[str] = set(known)
    for ts in triples.values():
        for t in ts:
            mentioned |= t
    for p in players:
        mentioned |= not_held[p]  # not_held affects who may take a card -> treat as constrained

    cand_env = {
        "suspect": [c for c in sus if c not in known and c not in faceup],
        "weapon": [c for c in weapons(edition) if c not in known and c not in faceup],
        "room": [c for c in rooms(edition) if c not in known and c not in faceup],
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


# ---------------------------------------------------------------------------------------------------
# Big tables: sound propagation + deterministic sampling


def _propagate(
    players: list[str],
    sizes: dict[str, int],
    known: dict[str, str],
    not_held: dict[str, set[str]],
    triples: dict[str, list[frozenset[str]]],
    all_cards: list[str],
    faceup: set[str],
) -> bool:
    """Unit propagation over the notebook constraints (mutates known / not_held). Returns False if inconsistent.

    Rules: a card known to be held by X is not held by anyone else; a "holds one of" triple whose other
    cards X provably lacks forces the last card into X's hand; a player whose known cards fill their hand
    lacks everything else; a triple X can't satisfy at all is a contradiction.
    """
    changed = True
    while changed:
        changed = False
        for card, holder in list(known.items()):
            for p in players:
                if p != holder and card not in not_held[p]:
                    not_held[p].add(card)
                    changed = True
        for p in players:
            mine = {c for c, h in known.items() if h == p}
            if len(mine) > sizes[p]:
                return False
            if len(mine) == sizes[p]:
                for c in all_cards:
                    if c not in mine and c not in not_held[p]:
                        not_held[p].add(c)
                        changed = True
            for t in triples[p]:
                if t & mine:
                    continue
                cand = [c for c in t if c not in not_held[p] and c not in faceup and known.get(c) in (None, p)]
                if not cand:
                    return False
                if len(cand) == 1:
                    known[cand[0]] = p
                    changed = True
    return True


def _solve_sampled(
    players: list[str],
    sizes: dict[str, int],
    known: dict[str, str],
    not_held: dict[str, set[str]],
    triples: dict[str, list[frozenset[str]]],
    all_cards: list[str],
    faceup: set[str],
    edition: str,
) -> Solution:
    """Approximate posterior for big tables: enumerate envelope candidates that survive propagation, then
    draw consistent deals with a randomised constructive search (deterministic seed from the evidence).

    `certain_holder` only contains facts proven by propagation (never sampling artefacts), so coach-mode
    "hard deductions" remain sound; probabilities are marked `exact=False`.
    """
    sol = Solution(exact=False)
    sus, wps, rms = suspects(edition), weapons(edition), rooms(edition)
    # a card is in the envelope iff nobody can hold it
    nobody = {c for c in all_cards if c not in known and c not in faceup and all(c in not_held[p] for p in players)}
    cats = {"suspect": sus, "weapon": wps, "room": rms}
    cand_env: dict[str, list[str]] = {}
    for cat, cards in cats.items():
        forced = [c for c in cards if c in nobody]
        if len(forced) > 1:
            return sol
        cand_env[cat] = forced or [c for c in cards if c not in known and c not in faceup]
        if not cand_env[cat]:
            return sol
    pool = [c for c in all_cards if c not in known and c not in faceup]
    caps = {p: sizes[p] - sum(1 for h in known.values() if h == p) for p in players}
    if any(v < 0 for v in caps.values()):
        return sol
    seed_src: tuple[object, ...] = (
        edition,
        tuple(players),
        tuple(sorted(sizes.items())),
        tuple(sorted(known.items())),
        tuple(sorted(faceup)),
        tuple((p, tuple(sorted(not_held[p]))) for p in players),
        tuple((p, tuple(sorted(tuple(sorted(t)) for t in triples[p]))) for p in players),
    )
    cached = _SAMPLED_CACHE.get(seed_src)
    if cached is not None:
        return cached
    if len(_SAMPLED_CACHE) > 2000:
        _SAMPLED_CACHE.clear()
    rng = random.Random(repr(seed_src))  # deterministic (hash() of str is salted per process; repr is not)
    in_triple = {c for ts in triples.values() for t in ts for c in t}
    combos: dict[Combo, int] = {}
    holder_counts: dict[str, dict[str, int]] = {c: {p: 0 for p in players} | {ENVELOPE: 0} for c in pool}
    n_ok = 0
    nodes_left = [SAMPLE_NODE_BUDGET]
    for _ in range(SAMPLES):
        if nodes_left[0] <= 0:
            break
        env = (rng.choice(cand_env["suspect"]), rng.choice(cand_env["weapon"]), rng.choice(cand_env["room"]))
        deal = _random_deal(rng, players, caps, not_held, triples, [c for c in pool if c not in env], in_triple, nodes_left)
        if deal is None:
            continue
        n_ok += 1
        combos[env] = combos.get(env, 0) + 1
        for c in env:
            holder_counts[c][ENVELOPE] += 1
        for c, p in deal.items():
            holder_counts[c][p] += 1
    if n_ok == 0:
        # sampling failed within budget: fall back to the propagation-only candidate set (uniform)
        for env in itertools.product(cand_env["suspect"], cand_env["weapon"], cand_env["room"]):
            combos[env] = 1
        n_ok = 1
    # keep every envelope that survived propagation in `combos` (smoothed) so callers never see a falsely
    # tiny candidate set; sampled mass dominates the ranking
    for env in itertools.product(cand_env["suspect"], cand_env["weapon"], cand_env["room"]):
        combos[env] = combos.get(env, 0) * 4 + 1
    sol.combos = combos
    sol.n_assignments = sum(combos.values())
    for env, cnt in combos.items():
        for c in env:
            sol.card_probs[c] = sol.card_probs.get(c, 0.0) + cnt / sol.n_assignments
    for c in all_cards:
        sol.card_probs.setdefault(c, 0.0)
        if c in known:
            sol.holder_probs[c] = {known[c]: 1.0}
            sol.certain_holder[c] = known[c]
        elif c in faceup:
            sol.holder_probs[c] = {"faceup": 1.0}
        elif c in nobody:
            sol.holder_probs[c] = {ENVELOPE: 1.0}
            sol.certain_holder[c] = ENVELOPE
        else:
            sol.holder_probs[c] = {h: n / n_ok for h, n in holder_counts[c].items() if n}
    _SAMPLED_CACHE[seed_src] = sol
    return sol


def _random_deal(
    rng: random.Random,
    players: list[str],
    caps: dict[str, int],
    not_held: dict[str, set[str]],
    triples: dict[str, list[frozenset[str]]],
    cards: list[str],
    in_triple: set[str],
    nodes_left: list[int] | None = None,
    budget: int = 3000,
) -> dict[str, str] | None:
    """One random consistent assignment of `cards` to players: randomised DFS with forward checking and a
    node budget (triple-constrained cards first, most-constrained first)."""
    left = dict(caps)
    if sum(left.values()) != len(cards):
        return None
    order = [c for c in cards if c in in_triple]
    rng.shuffle(order)
    order.sort(key=lambda c: sum(1 for p in players if c not in not_held[p]))  # fewest options first
    free = [c for c in cards if c not in in_triple]
    rng.shuffle(free)
    order += free
    unsat: dict[str, list[frozenset[str]]] = {p: list(triples[p]) for p in players}
    deal: dict[str, str] = {}
    nodes = 0
    shared = nodes_left if nodes_left is not None else [budget]
    budget = min(budget, shared[0])

    def feasible(remaining: list[str]) -> bool:
        rem = set(remaining)
        for q in players:
            if unsat[q] and left[q] == 0:
                return False
            for t in unsat[q]:
                if not any(x in rem and x not in not_held[q] for x in t):
                    return False
        return True

    def rec(i: int) -> bool:
        nonlocal nodes
        if i == len(order):
            return not any(unsat.values())
        nodes += 1
        if nodes > budget:
            return False
        card = order[i]
        choices = [p for p in players if left[p] > 0 and card not in not_held[p]]
        rng.shuffle(choices)
        # prefer players whose open triples this card would satisfy
        choices.sort(key=lambda p: -sum(1 for t in unsat[p] if card in t))
        rest = order[i + 1 :]
        for p in choices:
            left[p] -= 1
            saved = unsat[p]
            unsat[p] = [t for t in saved if card not in t]
            deal[card] = p
            if feasible(rest) and rec(i + 1):
                return True
            del deal[card]
            unsat[p] = saved
            left[p] += 1
            if nodes > budget:
                return False
        return False

    ok = rec(0)
    shared[0] -= nodes
    return deal if ok else None

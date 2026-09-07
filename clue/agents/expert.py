"""BaselineExpertBot: deterministic, exact-inference Clue player.

Decision policy
  Accuse    when exactly one envelope combo remains, or (rarely) when an opponent is about to win and our best
            combo's posterior beats the risk (see `_should_gamble`).
  Suggest   the (suspect, weapon) in the current room that maximises EXPECTED INFORMATION GAIN: for each
            candidate suggestion we enumerate the disproof outcomes (who answers, which card they could show)
            using the exact holder posterior, and compute the expected reduction in log2(#assignments).
  Move      toward the room with the best (information value) / (turns to reach) ratio, using BFS distances
            through the real board incl. secret passages; enters a reachable room when it beats the target.
  Show      the card that minimises what the suggester learns: prefer cards already shown to them, then
            cards most opponents already know we hold, then the category we hold most of.
Everything is derived from the exact solver in clue/tools/solver.py; no randomness except a seeded
tie-breaker so runs are reproducible.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any

from clue.agents.base import PlayerAgent, PonderContext
from clue.manager.notebook import Notebook
from clue.rules import Action
from clue.rules import board as B
from clue.rules.cards import ROOMS, WEAPONS
from clue.tools.opponent import opponent_threat
from clue.tools.solver import ENVELOPE, Solution, solve

Combo = tuple[str, str, str]


class BaselineExpertBot(PlayerAgent):
    kind = "baseline"
    supports_ponder = True

    def __init__(self, player_id: str, seed: int = 0, gamble: bool = True, enter_factor: float = 1.5, exact_top: int = 36) -> None:
        super().__init__(player_id)
        self.exact_top = exact_top  # re-score this many suggestion candidates with exact re-solving (0 = off)
        self.enter_factor = enter_factor
        self.rng = random.Random(seed)
        self.gamble = gamble
        self.shown_to: dict[str, set[str]] = {}  # suggester -> cards we've shown them
        self.shown_any: dict[str, int] = {}  # card -> how many times shown to anyone
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _ctx(obs: dict[str, Any]) -> tuple[Notebook, list[str], dict[str, int], str]:
        nb = Notebook(**obs["notebook"])
        players = [p["id"] for p in obs["board"]["players"]]
        sizes = {p["id"]: p["hand_size"] for p in obs["board"]["players"]}
        return nb, players, sizes, obs["config"]["edition"]

    def _solve(self, obs: dict[str, Any]) -> Solution:
        nb, players, sizes, edition = self._ctx(obs)
        key = (len(obs["public_history"]), tuple(sorted(nb.known_holder.items())), len(nb.has_one_of), sum(len(v) for v in nb.not_held.values()))
        if self._cache.get("key") == key:
            sol: Solution = self._cache["sol"]
            return sol
        sol = solve(nb, players, sizes, edition)
        self._cache = {"key": key, "sol": sol}
        return sol

    # ------------------------------------------------------------------ information gain
    def _expected_gain(self, obs: dict[str, Any], sol: Solution, suspect: str, weapon: str, room: str) -> float:
        """Expected bits gained from suggesting (suspect, weapon, room), under the exact posterior.

        We approximate the *outcome distribution* with the marginal holder probabilities and score each outcome
        by the fraction of current assignments it keeps (via the marginals), which is exact for single-card
        outcomes and a tight proxy for compound ones. Cheap enough to evaluate all 36 suggestions per turn.
        """
        nb, players, _, _ = self._ctx(obs)
        me = self.id
        cards = [suspect, weapon, room]
        order = players[players.index(me) + 1 :] + players[: players.index(me)]
        hp = sol.holder_probs
        # probability nobody before player k can disprove
        p_reach = 1.0
        gain = 0.0
        for p in order:
            # P(p holds none of the 3) ~ prod over cards of (1 - P(p holds c)) (independence approx.)
            p_none = 1.0
            for c in cards:
                p_none *= 1.0 - hp.get(c, {}).get(p, 0.0)
            p_disp = 1.0 - p_none
            if p_disp <= 1e-12:
                continue
            # Outcome: p disproves. What we learn depends on which card they show; we learn "p holds X".
            # Value ≈ entropy reduction: -log2 P(p holds X) for the card they'd show; assume they show the
            # card we already know about if any (worst case for us) else a uniformly chosen holdable card.
            known_to_me = [c for c in cards if hp.get(c, {}).get(p, 0.0) >= 0.999]
            if known_to_me:
                info_bits = 0.0
            else:
                holdable = [(c, hp.get(c, {}).get(p, 0.0)) for c in cards if hp.get(c, {}).get(p, 0.0) > 1e-9]
                info_bits = sum(-math.log2(max(pr, 1e-9)) for _, pr in holdable) / len(holdable)
            # plus what everyone before p revealed by failing (p_none facts), approximated by their bits
            gain += p_reach * p_disp * info_bits
            p_reach *= p_none
        # nobody disproves: we learn the three cards are ours or in the envelope — strong when it happens
        if p_reach > 1e-9:
            env_bits = sum(-math.log2(max(sol.card_probs.get(c, 0.0), 1e-9)) for c in cards if c not in nb.my_hand)
            gain += p_reach * env_bits
        # small penalty for including cards we hold (they can only be disproved by us => waste)
        gain -= 0.05 * sum(1 for c in cards if c in nb.my_hand)
        return gain

    def _exact_gain(self, obs: dict[str, Any], sol: Solution, suspect: str, weapon: str, room: str) -> float:
        """Exact expected bits: enumerate disproof outcomes and re-solve under each.

        Outcome (i, c): opponents before i hold none of the three, opponent i shows card c. Its weight is the
        number of assignments consistent with that; the information is log2(N) - log2(N_outcome). If opponent i
        holds several of the cards we assume they show the one we already know first (adversarial), otherwise
        we treat the outcomes as separate (slight over-count of multi-holders, which only softens the estimate).
        """
        nb, players, sizes, edition = self._ctx(obs)
        me = self.id
        cards = [suspect, weapon, room]
        order = players[players.index(me) + 1 :] + players[: players.index(me)]
        n0 = sol.n_assignments
        if n0 == 0:
            return 0.0
        h0 = _combo_entropy(sol)
        weights: list[tuple[int, float]] = []

        def outcome(nb2: Notebook) -> None:
            s2 = solve(nb2, players, sizes, edition)
            if s2.n_assignments:
                weights.append((s2.n_assignments, h0 - _combo_entropy(s2)))

        prefix_none: list[str] = []
        for p in order:
            known_to_me = [c for c in cards if nb.known_holder.get(c) == p]
            if known_to_me:
                # they will show what we already know: outcome carries only the "prefix none" facts
                nb2 = nb.model_copy(deep=True)
                for q in prefix_none:
                    nb2.mark_not_held(q, cards)
                outcome(nb2)
                break
            for c in cards:
                if c in nb.my_hand or c in nb.faceup or c in nb.not_held.get(p, []):
                    continue
                nb2 = nb.model_copy(deep=True)
                for q in prefix_none:
                    nb2.mark_not_held(q, cards)
                nb2.known_holder[c] = p
                outcome(nb2)
            prefix_none.append(p)
        else:
            nb2 = nb.model_copy(deep=True)
            for q in prefix_none:
                nb2.mark_not_held(q, cards)
            outcome(nb2)
        tot = sum(w for w, _ in weights)
        if tot == 0:
            return 0.0
        return sum(w * bits for w, bits in weights) / tot

    def _best_suggestion(self, obs: dict[str, Any], sol: Solution, room: str, exact: bool = False) -> tuple[str, str, float]:
        best: list[tuple[float, str, str]] = []
        for s in obs["cards"]["suspects"]:
            for w in WEAPONS:
                best.append((self._expected_gain(obs, sol, s, w, room), s, w))
        best.sort(reverse=True)
        if exact and self.exact_top > 0:
            cand = best[: self.exact_top]
            best = [(self._exact_gain(obs, sol, s, w, room), s, w) for _, s, w in cand]
            best.sort(reverse=True)
        top = [b for b in best if b[0] >= best[0][0] - 1e-9]
        g, s, w = self.rng.choice(top)
        return s, w, g

    def _room_values(self, obs: dict[str, Any], sol: Solution) -> dict[str, float]:
        """Best achievable gain per room (max over suspect/weapon), cached per solve."""
        if "room_values" in self._cache and self._cache.get("rv_key") == self._cache.get("key"):
            rv: dict[str, float] = self._cache["room_values"]
            return rv
        rv = {}
        for room in ROOMS:
            _, _, g = self._best_suggestion(obs, sol, room)
            rv[room] = g
        self._cache["room_values"] = rv
        self._cache["rv_key"] = self._cache.get("key")
        return rv

    # ------------------------------------------------------------------ movement
    @staticmethod
    def _turns_to_rooms(pos: str, occupied: frozenset[str], dice: int) -> dict[str, float]:
        """Expected turns to reach each room from `pos` (BFS steps / mean roll, passages count as 1 turn)."""
        mean_roll = 3.5 * dice
        dist: dict[str, float] = {}
        # corridor BFS from pos (or from each door if in a room)
        starts: list[tuple[tuple[int, int], int]] = []
        if B.is_room(pos):
            for d in B.DOORS[pos]:
                starts.append((d, 1))
            if pos in B.SECRET_PASSAGES:
                dist[B.SECRET_PASSAGES[pos]] = 1.0
        else:
            starts.append((B.parse_sq(pos), 0))
        blocked = {B.parse_sq(p) for p in occupied if not B.is_room(p) and p != pos}
        seen: dict[tuple[int, int], int] = {}
        q: deque[tuple[tuple[int, int], int]] = deque()
        for c, d0 in starts:
            if c in blocked:
                continue
            seen[c] = d0
            q.append((c, d0))
        while q:
            cell, dd = q.popleft()
            for room in B.BOARD.door_room.get(cell, []):
                if room != pos:
                    t = math.ceil((dd + 1) / mean_roll)
                    dist[room] = min(dist.get(room, 99), float(max(1, t)))
            for n in B.BOARD.neighbors(cell):
                if n in blocked or n in seen:
                    continue
                seen[n] = dd + 1
                q.append((n, dd + 1))
        return dist

    def _target_room(self, obs: dict[str, Any], sol: Solution, frm: str) -> tuple[str | None, float]:
        rv = self._room_values(obs, sol)
        occ = frozenset(obs["board"]["token_positions"].values())
        turns = self._turns_to_rooms(frm, occ, obs["config"]["dice"])
        best, best_score = None, -1.0
        for room, t in turns.items():
            score = rv.get(room, 0.0) / (t + 0.5)
            if score > best_score:
                best, best_score = room, score
        return best, best_score

    # ------------------------------------------------------------------ accusation policy
    def _should_gamble(self, obs: dict[str, Any], sol: Solution) -> Combo | None:
        """Accuse below certainty only if an opponent is very likely to win before our next turn."""
        if not self.gamble or len(sol.combos) < 2:
            return None
        best, p = sol.best
        if best is None or p < 0.34:
            return None
        nb, players, sizes, edition = self._ctx(obs)
        for con in nb.unrefuted_suggestions[-3:]:
            if con.player != self.id and tuple(con.cards) == best:
                return best
        # Decision-theoretic gamble: accuse now iff P(win now) = p exceeds P(win by waiting). If we survive the
        # coming round we keep every option (incl. accusing `best` later with >= p), so
        #   P(win by waiting) ~= 1 - P(an opponent wins before my next turn)
        # is an upper bound and the rule only fires when a rival is genuinely about to win.
        elim = {q["id"] for q in obs["board"]["players"] if q.get("eliminated")}
        threat = opponent_threat(nb, players, self.id, sizes, edition, obs.get("public_history", []), elim, sol=sol)
        p_opp = float(threat["p_any_wins_before_my_turn"])
        if p_opp <= 0.0:
            return None
        return best if p > 1.0 - p_opp else None

    # ------------------------------------------------------------------ interface
    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        obs = observation
        sol = self._solve(obs)
        types = {a.type for a in legal_actions}
        if obs["can_accuse"]:
            if len(sol.combos) == 1:
                s, w, r = next(iter(sol.combos))
                return Action(type="accuse", player=self.id, suspect=s, weapon=w, room=r)
            g = self._should_gamble(obs, sol)
            if g:
                return Action(type="accuse", player=self.id, suspect=g[0], weapon=g[1], room=g[2])
        pos = obs["you"]["position"]
        if "suggest" in types:
            s, w, _ = self._best_suggestion(obs, sol, pos, exact=True)
            return Action(type="suggest", player=self.id, suspect=s, weapon=w, room=pos)
        if "passage" in types or "roll" in types:
            if "passage" in types:
                dest = B.SECRET_PASSAGES[pos]
                rv = self._room_values(obs, sol)
                target, score = self._target_room(obs, sol, pos)
                # passage is a guaranteed room this turn: take it if its value is competitive
                if rv.get(dest, 0.0) >= 0.8 * (rv.get(target or dest, 0.0)) or target == dest:
                    return Action(type="passage", player=self.id)
            if "roll" in types:
                return Action(type="roll", player=self.id)
        if "move" in types:
            moves = [a for a in legal_actions if a.type == "move"]
            rooms = [a for a in moves if B.is_room(a.to or "")]
            rv = self._room_values(obs, sol)
            target, tscore = self._target_room(obs, sol, pos)
            if rooms:
                best_room = max(rooms, key=lambda a: rv.get(a.to or "", 0.0))
                # enter now if its value is at least what we'd expect from heading for the target next turn
                if rv.get(best_room.to or "", 0.0) >= tscore * self.enter_factor or target is None:
                    return best_room
            occ = frozenset(obs["board"]["token_positions"].values())
            dice = obs["config"]["dice"]

            def move_score(a: Action) -> float:
                dest = a.to or ""
                if B.is_room(dest):
                    return rv.get(dest, 0.0) * 2  # already counted above; strongly prefer rooms anyway
                t = self._turns_to_rooms(dest, occ, dice)
                return max((rv.get(r, 0.0) / (tt + 0.5) for r, tt in t.items()), default=0.0)

            return max(moves, key=move_score)
        if "end_turn" in types:
            return Action(type="end_turn", player=self.id)
        return legal_actions[0]

    def export_state(self) -> dict[str, Any]:
        return {**super().export_state(), "shown_to": {k: sorted(v) for k, v in self.shown_to.items()}, "shown_any": dict(self.shown_any)}

    def import_state(self, state: dict[str, Any]) -> None:
        super().import_state(state)
        self.shown_to = {k: set(v) for k, v in state.get("shown_to", {}).items()}
        self.shown_any = dict(state.get("shown_any", {}))
        self._cache = {}

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        suggester = observation["turn"]["pending_suggestion"]["suggester"]
        already = self.shown_to.setdefault(suggester, set())
        hand = observation["you"]["hand"]

        def rank(c: str) -> tuple[int, int, int, str]:
            cat_count = -sum(1 for h in hand if _cat(h) == _cat(c))  # prefer category we have most of
            return (0 if c in already else 1, -self.shown_any.get(c, 0), cat_count, c)

        card = min(cards_that_can_disprove, key=rank)
        already.add(card)
        self.shown_any[card] = self.shown_any.get(card, 0) + 1
        return card

    def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
        """Warm the solver cache and room values on the snapshot; note forced facts."""
        ctx.rounds += 1
        sol = self._solve(observation)
        ctx.check()
        self._room_values(observation, sol)
        facts = [
            f"{c} is in the envelope" if h == ENVELOPE else f"{h} must hold {c}" for c, h in sol.certain_holder.items() if h not in ("faceup",) and c not in observation["notebook"]["known_holder"]
        ]
        for f in facts[:5]:
            ctx.note(f)
        return {"n_possible": len(sol.combos), "certain": len(facts)}


def _combo_entropy(sol: Solution) -> float:
    n = sol.n_assignments
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in sol.combos.values() if c)


def _cat(card: str) -> str:
    if card in WEAPONS:
        return "weapon"
    if card in ROOMS:
        return "room"
    return "suspect"

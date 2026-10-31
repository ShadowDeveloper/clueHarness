"""Standalone analyst: type in what you observed at a real table and get probabilities + coaching.

An `AnalysisSession` is a declarative description of a game *as seen by one player*: the edition, the
seating order, your own cards, any face-up cards, and a list of observations (suggestions with who
disproved / what you were shown, plus free-form "player has / hasn't card" facts). The session is
converted into the exact event stream the engine would have produced and replayed through
`Notebook.ingest`, so every analytical tool (solver, deductions, opponent model, suggestion EV) sees the
same evidence it would see in a live game — no duplicated inference logic.

Consumers:
  * `clue analyze`            - Textual TUI (clue/tui/analyst_app.py) and plain CLI report
  * `POST /api/analyze`       - FastAPI route (clue/web/routes/analyze.py)
  * web/src/analysis/*        - a TypeScript port of the same math for the static GitHub Pages build
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from clue.manager.notebook import Notebook
from clue.rules.cards import EDITIONS, edition_def, rooms, suspects, weapons


class SuggestionObservation(BaseModel):
    """One suggestion you witnessed: who suggested what, and how it was (or wasn't) disproved."""

    type: Literal["suggestion"] = "suggestion"
    suggester: str
    suspect: str
    weapon: str
    room: str
    disprover: str | None = None  # None = nobody could disprove
    shown_card: str | None = None  # only known when you were the suggester or the disprover


class FactObservation(BaseModel):
    """A direct fact: `player` definitely holds / definitely lacks `card` (e.g. a card you were shown)."""

    type: Literal["fact"] = "fact"
    player: str
    card: str
    has: bool = True


ObservationEvent = Annotated[Union[SuggestionObservation, FactObservation], Field(discriminator="type")]


class AnalysisSession(BaseModel):
    """Everything one player knows about an in-progress game, entered by hand."""

    edition: str = "classic"
    players: list[str] = Field(default_factory=list)  # seating order, starting anywhere
    me: str = ""
    my_cards: list[str] = Field(default_factory=list)
    faceup: list[str] = Field(default_factory=list)
    hand_sizes: dict[str, int] | None = None  # optional explicit sizes; defaults to an even deal
    observations: list[ObservationEvent] = Field(default_factory=list)
    # Display renames: canonical card -> the name printed on YOUR copy of the game (localisation, house
    # variants, "Rev. Green", ...). Purely cosmetic - the solver and the session always store canonical
    # names; every UI (TUI, CLI, web) renders through this mapping.
    card_names: dict[str, str] = Field(default_factory=dict)


def display_name(session: AnalysisSession, card: str) -> str:
    """The label to show for a canonical card (falls back to the canonical name)."""
    return (session.card_names.get(card) or card).strip() or card


def label_text(session: AnalysisSession, text: str) -> str:
    """Rewrite canonical card names inside a human-readable sentence with the user's renames.

    Card names are never substrings of one another within an edition, so longest-first whole-name
    replacement is unambiguous (players named exactly like a card would also be rewritten - don't).
    """
    renames = {c: v.strip() for c, v in session.card_names.items() if v.strip() and v.strip() != c}
    if not renames:
        return text
    import re

    pattern = re.compile("|".join(re.escape(c) for c in sorted(renames, key=len, reverse=True)))
    return pattern.sub(lambda m: renames[m.group(0)], text)


def default_hand_sizes(session: AnalysisSession) -> dict[str, int]:
    """Even deal of the non-faceup, non-envelope cards; your seat is pinned to len(my_cards)."""
    if session.hand_sizes:
        return dict(session.hand_sizes)
    pool = edition_def(session.edition).n_dealt - len(session.faceup)
    others = [p for p in session.players if p != session.me]
    if session.me in session.players and session.my_cards:
        mine = len(session.my_cards)
        base, rem = divmod(max(pool - mine, 0), max(len(others), 1))
        sizes = {p: base + (1 if i < rem else 0) for i, p in enumerate(others)}
        sizes[session.me] = mine
        return {p: sizes[p] for p in session.players}
    base, rem = divmod(pool, max(len(session.players), 1))
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(session.players)}


def _category(card: str, edition: str) -> str | None:
    if card in suspects(edition):
        return "suspect"
    if card in weapons(edition):
        return "weapon"
    if card in rooms(edition):
        return "room"
    return None


def validate_session(session: AnalysisSession) -> list[str]:
    """Hard errors that make analysis meaningless. An empty list means the session is analyzable."""
    errors: list[str] = []
    if session.edition not in EDITIONS:
        return [f"unknown edition {session.edition!r}; choose one of {', '.join(EDITIONS)}"]
    ed = session.edition
    deck = set(suspects(ed)) | set(weapons(ed)) | set(rooms(ed))
    n_max = edition_def(ed).max_players
    if not 3 <= len(session.players) <= n_max:
        errors.append(f"{ed} edition needs 3..{n_max} players (got {len(session.players)})")
    if len(set(session.players)) != len(session.players):
        errors.append("player names must be unique")
    if session.me not in session.players:
        errors.append(f"your seat {session.me!r} is not in the player list")
    for label, cards in (("my_cards", session.my_cards), ("faceup", session.faceup)):
        for c in cards:
            if c not in deck:
                errors.append(f"{label}: {c!r} is not a {ed}-edition card")
    if set(session.my_cards) & set(session.faceup):
        errors.append("a card cannot be both in your hand and face-up")
    if session.hand_sizes is not None:
        if set(session.hand_sizes) != set(session.players):
            errors.append("hand_sizes must cover exactly the listed players")
        elif sum(session.hand_sizes.values()) != edition_def(ed).n_dealt - len(session.faceup):
            errors.append(f"hand sizes must sum to {edition_def(ed).n_dealt - len(session.faceup)} (deck minus envelope and face-up)")
        elif session.me in session.hand_sizes and session.my_cards and session.hand_sizes[session.me] != len(session.my_cards):
            errors.append(f"hand_sizes[{session.me}] = {session.hand_sizes[session.me]} but you entered {len(session.my_cards)} cards")
    if session.card_names:
        seen_labels: dict[str, str] = {}
        for card, label in session.card_names.items():
            if card not in deck:
                errors.append(f"card_names: {card!r} is not a {ed}-edition card")
                continue
            lab = label.strip()
            if not lab:
                errors.append(f"card_names: the label for {card!r} is empty")
                continue
            low = lab.lower()
            if low in seen_labels and seen_labels[low] != card:
                errors.append(f"card_names: two cards share the label {lab!r}")
            seen_labels[low] = card
            other = next((c for c in deck if c.lower() == low and c != card and session.card_names.get(c, c).strip().lower() == low), None)
            if other is not None:
                errors.append(f"card_names: {card!r} is renamed to {lab!r}, which is still the name of {other!r}")
    for i, ob in enumerate(session.observations, 1):
        where = f"observation {i}"
        if isinstance(ob, SuggestionObservation):
            if ob.suggester not in session.players:
                errors.append(f"{where}: unknown suggester {ob.suggester!r}")
            if ob.disprover is not None and ob.disprover not in session.players:
                errors.append(f"{where}: unknown disprover {ob.disprover!r}")
            if ob.disprover == ob.suggester:
                errors.append(f"{where}: the suggester cannot disprove their own suggestion")
            for card, cat in ((ob.suspect, "suspect"), (ob.weapon, "weapon"), (ob.room, "room")):
                if _category(card, ed) != cat:
                    errors.append(f"{where}: {card!r} is not a {ed}-edition {cat}")
            if ob.shown_card is not None:
                if ob.disprover is None:
                    errors.append(f"{where}: shown_card given but nobody disproved")
                elif ob.shown_card not in (ob.suspect, ob.weapon, ob.room):
                    errors.append(f"{where}: shown card {ob.shown_card!r} is not one of the three suggested cards")
        else:
            if ob.player not in session.players:
                errors.append(f"{where}: unknown player {ob.player!r}")
            if ob.card not in deck:
                errors.append(f"{where}: {ob.card!r} is not a {ed}-edition card")
    return errors


def session_events(session: AnalysisSession) -> list[dict[str, Any]]:
    """The redacted-for-viewer engine events this session corresponds to (suggest / cannot_disprove /
    disproved / no_one_disproved), suitable for `Notebook.ingest` and `opponent_threat` history."""
    events: list[dict[str, Any]] = []
    order = session.players
    for turn, ob in enumerate(session.observations, 1):
        if not isinstance(ob, SuggestionObservation):
            continue
        events.append({"type": "suggest", "turn": turn, "player": ob.suggester, "suspect": ob.suspect, "weapon": ob.weapon, "room": ob.room})
        start = order.index(ob.suggester)
        ring = [order[(start + k) % len(order)] for k in range(1, len(order))]
        if ob.disprover is None:
            events.extend({"type": "cannot_disprove", "turn": turn, "player": p} for p in ring)
            events.append({"type": "no_one_disproved", "turn": turn, "player": ob.suggester, "suspect": ob.suspect, "weapon": ob.weapon, "room": ob.room})
            continue
        for p in ring:
            if p == ob.disprover:
                break
            events.append({"type": "cannot_disprove", "turn": turn, "player": p})
        ev: dict[str, Any] = {"type": "disproved", "turn": turn, "player": ob.disprover, "disprover": ob.disprover, "suggester": ob.suggester}
        if ob.shown_card is not None:
            ev["card"] = ob.shown_card
        events.append(ev)
    return events


def build_notebook(session: AnalysisSession) -> Notebook:
    """Replay the session through the standard notebook so the tools see normal in-game evidence."""
    nb = Notebook(viewer=session.me, my_hand=list(session.my_cards), faceup=list(session.faceup))
    for c in session.my_cards:
        nb.known_holder[c] = session.me
    for ev in session_events(session):
        nb.ingest(ev, session.players)
    for turn, ob in enumerate(session.observations, 1):
        if isinstance(ob, FactObservation):
            if ob.has:
                prev = nb.known_holder.get(ob.card)
                if prev is not None and prev != ob.player:
                    nb.notes.append(f"CONFLICT: {ob.card} cannot be held by both {prev} and {ob.player}")
                else:
                    nb.known_holder[ob.card] = ob.player
                nb.notes.append(f"[{turn}] fact: {ob.player} holds {ob.card}")
            else:
                nb.mark_not_held(ob.player, [ob.card])
                nb.notes.append(f"[{turn}] fact: {ob.player} lacks {ob.card}")
    return nb


def direct_conflicts(nb: Notebook) -> list[str]:
    """Contradictions visible without any counting (hand-entered sessions can contain impossible facts)."""
    out = [n.removeprefix("CONFLICT: ") for n in nb.notes if n.startswith("CONFLICT: ")]
    for card, holder in sorted(nb.known_holder.items()):
        if card in nb.not_held.get(holder, []):
            out.append(f"{holder} is marked both holding and not holding {card}")
        if card in nb.faceup:
            out.append(f"{card} is face-up but also assigned to {holder}")
    return out


def analyze(session: AnalysisSession, accuse_threshold: float = 0.9, top_suggestions: int = 3) -> dict[str, Any]:
    """Full analyst report: validation, posterior probabilities, hard deductions, threat, and a guide."""
    errors = validate_session(session)
    if errors:
        return {"ok": False, "errors": errors}
    from clue.tools.deduction import best_suggestion, can_accuse_confidently, get_unseen_cards, hard_deductions, solution_probabilities, suggestion_ev
    from clue.tools.opponent import opponent_threat
    from clue.tools.solver import solve

    ed, players, me = session.edition, session.players, session.me
    sizes = default_hand_sizes(session)
    nb = build_notebook(session)
    conflicts = direct_conflicts(nb)
    if conflicts:
        return {
            "ok": True,
            "errors": [],
            "edition": ed,
            "players": players,
            "me": me,
            "hand_sizes": sizes,
            "consistent": False,
            "conflicts": [label_text(session, c) for c in conflicts],
            "card_names": dict(session.card_names),
            "solution": {"n_possible": 0, "combos": {}, "cards": {}, "best": None, "best_prob": 0.0, "exact": True},
            "holders": {},
            "deductions": [],
            "unseen": get_unseen_cards(nb, ed),
            "threat": {"opponents": {}, "max_threat": 0.0, "most_dangerous": None, "p_any_wins_before_my_turn": 0.0},
            "guide": {
                "accusal": {"accuse": False, "reason": "notebook inconsistent", "best": None, "confidence": 0.0, "threshold": accuse_threshold, "exact": True},
                "suggestions": [],
                "advice": ["Your observations are contradictory - at least one entry must be wrong:"] + [f"  - {label_text(session, c)}" for c in conflicts],
            },
        }
    sol = solve(nb, players, sizes, ed)
    post = solution_probabilities(nb, players, sizes, ed)
    accusal = can_accuse_confidently(nb, players, accuse_threshold, sizes, ed)
    deductions = [label_text(session, d) for d in hard_deductions(nb, players, sizes, ed)]
    threat = opponent_threat(nb, players, me, sizes, ed, session_events(session), sol=sol)
    ranked: list[dict[str, Any]] = []
    for room in rooms(ed):
        s, w = best_suggestion(nb, players, me, room, ed)
        ev = suggestion_ev(nb, players, me, s, w, room, ed)
        ranked.append({"suspect": s, "weapon": w, "room": room, **ev})
    ranked.sort(key=lambda d: (-float(d["score"]), str(d["room"])))
    report: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "edition": ed,
        "players": players,
        "me": me,
        "hand_sizes": sizes,
        "consistent": post["n_possible"] > 0,
        "conflicts": [],
        "card_names": dict(session.card_names),
        "solution": post,
        "holders": {c: {h: round(p, 4) for h, p in probs.items()} for c, probs in sol.holder_probs.items()},
        "deductions": deductions,
        "unseen": get_unseen_cards(nb, ed),
        "threat": threat,
        "guide": {
            "accusal": accusal,
            "suggestions": ranked[:top_suggestions],
            "advice": [label_text(session, a) for a in _advice(post, accusal, deductions, threat, ranked[:1])],
        },
    }
    return report


def _advice(post: dict[str, Any], accusal: dict[str, Any], deductions: list[str], threat: dict[str, Any], top: list[dict[str, Any]]) -> list[str]:
    """Coach-style, human-readable guidance derived from the analytical results."""
    lines: list[str] = []
    n = int(post["n_possible"])
    if n == 0:
        return ["Your observations are contradictory - at least one entry must be wrong. Re-check the most recent suggestion/fact you added."]
    best = post.get("best")
    if n == 1 and post.get("exact"):
        s, w, r = best or ("?", "?", "?")
        lines.append(f"SOLVED - the envelope must be {s} / {w} / {r}. Accuse on your turn.")
        return lines
    if best:
        qual = "" if post.get("exact") else " (estimated - large table)"
        lines.append(f"{n} candidate solutions remain{qual}; most likely: {best[0]} / {best[1]} / {best[2]} at p={post['best_prob']:.2f}.")
    if accusal.get("accuse"):
        b = accusal["best"]
        lines.append(f"Confidence {accusal['confidence']:.2f} >= {accusal['threshold']:.2f}: accusing {b[0]} / {b[1]} / {b[2]} is justified if you accept the risk.")
    else:
        lines.append(f"Too early to accuse (confidence {accusal['confidence']:.2f} < {accusal['threshold']:.2f}). Keep suggesting to narrow it down.")
    if deductions:
        lines.append("Mark in your notebook: " + "; ".join(deductions[:3]) + ("..." if len(deductions) > 3 else "."))
    if top:
        t = top[0]
        lines.append(f"Highest-value next suggestion: {t['suspect']} with the {t['weapon']} in the {t['room']} (score {t['score']:.2f}).")
    if float(threat.get("max_threat", 0.0)) >= 0.35 and threat.get("most_dangerous"):
        lines.append(f"Danger: {threat['most_dangerous']} looks close to solving (p~{threat['max_threat']:.2f} before your next turn). Consider accusing earlier than usual.")
    return lines

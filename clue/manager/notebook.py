"""Per-player public knowledge notebook, derived mechanically from the event stream.

The notebook is a *fact store* (no LLM). It records what a given viewer is entitled to know:
their own hand, face-up cards, cards they were shown, and constraints of the form
"player X holds at least one of {a,b,c}" / "player X holds none of {a,b,c}".
"""

from __future__ import annotations

from pydantic import BaseModel, Field, PrivateAttr


class Constraint(BaseModel):
    player: str
    cards: list[str]
    turn: int
    suggester: str


class Notebook(BaseModel):
    viewer: str
    my_hand: list[str] = Field(default_factory=list)
    faceup: list[str] = Field(default_factory=list)
    # cards known to be held by a specific player (viewer's hand, shown cards, deductions)
    known_holder: dict[str, str] = Field(default_factory=dict)
    # player -> cards they definitely do NOT hold
    not_held: dict[str, list[str]] = Field(default_factory=dict)
    has_one_of: list[Constraint] = Field(default_factory=list)
    unrefuted_suggestions: list[Constraint] = Field(default_factory=list)  # nobody could disprove
    suggestions_made: dict[str, int] = Field(default_factory=dict)
    disproof_counts: dict[str, int] = Field(default_factory=dict)  # player -> times they disproved
    my_suggestions: list[dict[str, object]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # free-form entries appended by the agent (update_notebook)

    def mark_not_held(self, player: str, cards: list[str]) -> None:
        cur = self.not_held.setdefault(player, [])
        for c in cards:
            if c not in cur:
                cur.append(c)

    def ingest(self, ev: dict[str, object], players: list[str]) -> None:
        """Consume one *redacted-for-viewer* event dict."""
        t = str(ev["type"])
        turn = int(str(ev["turn"]))
        who = ev.get("player")
        if t == "suggest":
            cards = [str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])]
            self.suggestions_made[str(who)] = self.suggestions_made.get(str(who), 0) + 1
            if who == self.viewer:
                self.my_suggestions.append({"turn": turn, "cards": cards, "shown": None, "by": None})
        elif t == "cannot_disprove":
            cards = self._cards_of_pending(turn)
            if cards:
                self.mark_not_held(str(who), cards)
        elif t == "disproved":
            cards = self._cards_of_pending(turn)
            self.disproof_counts[str(who)] = self.disproof_counts.get(str(who), 0) + 1
            if "card" in ev:  # we were involved
                self.known_holder[str(ev["card"])] = str(who)
                if ev.get("suggester") == self.viewer and self.my_suggestions:
                    self.my_suggestions[-1]["shown"] = ev["card"]
                    self.my_suggestions[-1]["by"] = who
            elif cards:
                self.has_one_of.append(Constraint(player=str(who), cards=cards, turn=turn, suggester=str(ev.get("suggester"))))
        elif t == "no_one_disproved":
            cards = [str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])]
            self.unrefuted_suggestions.append(Constraint(player=str(who), cards=cards, turn=turn, suggester=str(who)))
            for p in players:
                if p != who:
                    self.mark_not_held(p, cards)
        self._last_events.append(ev)

    # bookkeeping of the pending suggestion so cannot/disproved events can be resolved
    _last_events: list[dict[str, object]] = PrivateAttr(default_factory=list)

    def _cards_of_pending(self, turn: int) -> list[str]:
        for ev in reversed(self._last_events):
            if ev["type"] == "suggest" and ev["turn"] == turn:
                return [str(ev["suspect"]), str(ev["weapon"]), str(ev["room"])]
        return []

    def known_not_in_solution(self) -> set[str]:
        return set(self.my_hand) | set(self.faceup) | set(self.known_holder)

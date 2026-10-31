"""Textual analyst: type in a real-table game (your cards + observed suggestions) and watch the solver.

Launched by `clue analyze` (optionally with a saved session JSON). The app is a thin data-entry shell
around `clue.tools.analyst`: every change re-runs the exact-or-sampled solver and refreshes the
probability grid, candidate list, hard deductions, and the coach-style guide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, OptionList, SelectionList, Static
from textual.widgets.option_list import Option

from clue.rules.cards import EDITIONS, edition_def, rooms, suspects, weapons
from clue.tools.analyst import AnalysisSession, FactObservation, SuggestionObservation, analyze, display_name

NOBODY = "(nobody could disprove)"
UNSEEN = "(card not seen)"


def observation_label(ob: SuggestionObservation | FactObservation, names: dict[str, str] | None = None) -> str:
    def lab(c: str) -> str:
        return ((names or {}).get(c) or c).strip() or c

    if isinstance(ob, FactObservation):
        return f"fact: {ob.player} {'holds' if ob.has else 'lacks'} {lab(ob.card)}"
    tail = f"{ob.disprover} showed {lab(ob.shown_card)}" if ob.shown_card else (f"{ob.disprover} disproved" if ob.disprover else "nobody disproved")
    return f"{ob.suggester}: {lab(ob.suspect)} / {lab(ob.weapon)} / {lab(ob.room)} -> {tail}"


class AnalystApp(App[None]):
    """Full-screen analyst for a game played away from the computer."""

    CSS = """
    Screen { layout: vertical; }
    #top { height: 1fr; }
    #left { width: 46; }
    #session { height: auto; max-height: 12; border: round $secondary; padding: 0 1; }
    #observations { height: 1fr; border: round $primary; }
    #entry { height: auto; max-height: 60%; border: heavy $warning; padding: 0 1; }
    #entry_title { height: auto; color: $text-muted; }
    #entry_choices { height: auto; max-height: 14; }
    #entry_multi { height: auto; max-height: 14; display: none; }
    #entry_input { display: none; }
    #entry_row { height: auto; }
    #entry_row Button { min-width: 9; margin: 0 1 0 0; }
    #middle { width: 1fr; min-width: 40; }
    #probs { height: 1fr; border: round $secondary; }
    #candidates { height: auto; max-height: 10; border: round $accent; padding: 0 1; }
    #right { width: 56; }
    #guide { height: 1fr; border: round $success; padding: 0 1; }
    #status { height: 1; background: $boost; padding: 0 1; }
    """

    BINDINGS = [
        Binding("s", "add_suggestion", "Suggestion"),
        Binding("f", "add_fact", "Fact"),
        Binding("u", "undo", "Undo last"),
        Binding("e", "setup", "Edit setup"),
        Binding("n", "rename", "Rename card"),
        Binding("ctrl+s", "save", "Save session"),
        Binding("escape", "cancel", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, session: AnalysisSession | None = None, path: str | None = None, threshold: float = 0.9) -> None:
        super().__init__()
        self.session = session or AnalysisSession()
        self.path = path
        self.threshold = threshold
        self.report: dict[str, Any] | None = None
        self._flow: list[dict[str, Any]] = []  # remaining steps of the active entry flow
        self._step: dict[str, Any] | None = None
        self._collect: dict[str, Any] = {}
        self._flow_kind = ""

    # ---------------- layout
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="top"):
            with Vertical(id="left"):
                yield Static(id="session")
                yield OptionList(id="observations")
                with VerticalScroll(id="entry"):
                    yield Static("", id="entry_title")
                    yield OptionList(id="entry_choices")
                    yield SelectionList[str](id="entry_multi")
                    yield Input(id="entry_input")
                    with Horizontal(id="entry_row"):
                        yield Button("Confirm", id="b_confirm", variant="primary")
                        yield Button("Back (esc)", id="b_back")
            with Vertical(id="middle"):
                yield DataTable[str](id="probs", zebra_stripes=True, cursor_type="none")
                yield Static(id="candidates")
            with Vertical(id="right"):
                yield Static(id="guide")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Clue analyst"
        self.sub_title = "probabilities + coaching for a game you are playing in the real world"
        self.query_one("#session", Static).border_title = "Session"
        self.query_one("#observations", OptionList).border_title = "Observations"
        self.query_one("#entry", VerticalScroll).border_title = "Entry"
        self.query_one("#probs", DataTable).border_title = "P(card is in the envelope / held by...)"
        self.query_one("#candidates", Static).border_title = "Candidate solutions"
        self.query_one("#guide", Static).border_title = "Guide"
        if self.session.players:
            self.recompute()
        else:
            self.action_setup()

    # ---------------- entry flows: a list of steps, each one OptionList / SelectionList / Input based
    def _edition_cards(self) -> list[str]:
        ed = self.session.edition
        return list(suspects(ed)) + list(weapons(ed)) + list(rooms(ed))

    def _lab(self, card: str) -> str:
        """Display label for a canonical card (user renames, e.g. localisation)."""
        return display_name(self.session, card)

    def action_rename(self) -> None:
        if not self.session.players:
            self.action_setup()
            return
        self._flow_kind = "rename"
        self._collect = {}
        self._flow = [
            {"key": "card", "title": "Rename which card? (how it is printed on YOUR copy of the game)", "options": "cards", "kind": "pick"},
            {"key": "label", "title": "New name (leave empty to restore the standard name):", "kind": "input", "value": ""},
        ]
        self._next_step()

    def action_setup(self) -> None:
        self._flow_kind = "setup"
        self._collect = {}
        self._flow = [
            {"key": "edition", "title": "Which edition are you playing?", "options": list(EDITIONS), "kind": "pick"},
            {"key": "players", "title": "Seating order, starting with any seat (comma-separated names):", "kind": "input", "value": ", ".join(self.session.players) or "P1, P2, P3, P4"},
            {"key": "me", "title": "Which seat is you?", "options": "players", "kind": "pick"},
            {"key": "my_cards", "title": "Select the cards in YOUR hand:", "options": "cards", "kind": "multi", "selected": "my_cards"},
            {"key": "faceup", "title": "Any face-up cards dealt to nobody? (optional)", "options": "cards_left", "kind": "multi", "selected": "faceup"},
        ]
        self._next_step()

    def action_add_suggestion(self) -> None:
        if not self.session.players:
            self.action_setup()
            return
        ed = self.session.edition
        self._flow_kind = "suggestion"
        self._collect = {}
        self._flow = [
            {"key": "suggester", "title": "Who made the suggestion?", "options": list(self.session.players), "kind": "pick"},
            {"key": "suspect", "title": "Suggested suspect:", "options": list(suspects(ed)), "kind": "pick"},
            {"key": "weapon", "title": "Suggested weapon:", "options": list(weapons(ed)), "kind": "pick"},
            {"key": "room", "title": "Suggested room:", "options": list(rooms(ed)), "kind": "pick"},
            {"key": "disprover", "title": "Who showed a card?", "options": "disprovers", "kind": "pick"},
            {"key": "shown_card", "title": "Which card was shown (if you saw it)?", "options": "shown", "kind": "pick"},
        ]
        self._next_step()

    def action_add_fact(self) -> None:
        if not self.session.players:
            self.action_setup()
            return
        self._flow_kind = "fact"
        self._collect = {}
        self._flow = [
            {"key": "player", "title": "Fact about which player?", "options": list(self.session.players), "kind": "pick"},
            {"key": "has", "title": "Do they hold the card or definitely lack it?", "options": ["holds the card", "does not hold the card"], "kind": "pick"},
            {"key": "card", "title": "Which card?", "options": "cards", "kind": "pick"},
        ]
        self._next_step()

    def _dynamic_options(self, spec: str) -> list[str]:
        if spec == "players":
            return list(self._collect.get("players", self.session.players))
        if spec == "cards":
            return self._edition_cards()
        if spec == "cards_left":
            return [c for c in self._edition_cards() if c not in self._collect.get("my_cards", [])]
        if spec == "disprovers":
            return [p for p in self.session.players if p != self._collect.get("suggester")] + [NOBODY]
        if spec == "shown":
            return [self._collect[k] for k in ("suspect", "weapon", "room")] + [UNSEEN]
        return []

    def _next_step(self) -> None:
        if not self._flow:
            self._finish_flow()
            return
        self._step = step = self._flow.pop(0)
        # skip the shown-card step entirely when nobody disproved
        if step["key"] == "shown_card" and self._collect.get("disprover") == NOBODY:
            self._collect["shown_card"] = UNSEEN
            self._next_step()
            return
        title = self.query_one("#entry_title", Static)
        choices = self.query_one("#entry_choices", OptionList)
        multi = self.query_one("#entry_multi", SelectionList)
        inp = self.query_one("#entry_input", Input)
        title.update(f"[b]{step['title']}[/b]")
        choices.display = step["kind"] == "pick"
        multi.display = step["kind"] == "multi"
        inp.display = step["kind"] == "input"
        if step["kind"] == "pick":
            opts = step["options"] if isinstance(step["options"], list) else self._dynamic_options(step["options"])
            choices.clear_options()
            deck = set(self._edition_cards())
            choices.add_options([Option(self._lab(o) if o in deck else o, id=f"opt{i}") for i, o in enumerate(opts)])
            self._step["resolved"] = opts
            choices.highlighted = 0
            choices.focus()
        elif step["kind"] == "multi":
            opts = step["options"] if isinstance(step["options"], list) else self._dynamic_options(step["options"])
            picked = set(getattr(self.session, str(step.get("selected")), []) or [])
            multi.clear_options()
            deck = set(self._edition_cards())
            multi.add_options([(self._lab(o) if o in deck else o, o, o in picked) for o in opts])
            multi.focus()
        else:
            value = str(step.get("value", ""))
            if self._flow_kind == "rename" and step["key"] == "label":
                card = str(self._collect.get("card", ""))
                cur = self._lab(card)
                value = "" if cur == card else cur
            inp.value = value
            inp.focus()
        self._status(f"{self._flow_kind}: {len(self._flow)} step(s) left - Enter/Confirm to continue, Esc to cancel")

    def _finish_flow(self) -> None:
        c = self._collect
        try:
            if self._flow_kind == "setup":
                self.session.edition = str(c["edition"])
                self.session.players = list(c["players"])
                self.session.me = str(c["me"])
                self.session.my_cards = list(c["my_cards"])
                self.session.faceup = list(c["faceup"])
                self.session.hand_sizes = None
                self.session.observations = [ob for ob in self.session.observations if self._observation_valid(ob)]
            elif self._flow_kind == "suggestion":
                disprover = None if c["disprover"] == NOBODY else str(c["disprover"])
                shown = None if c.get("shown_card") in (UNSEEN, None) else str(c["shown_card"])
                self.session.observations.append(
                    SuggestionObservation(suggester=str(c["suggester"]), suspect=str(c["suspect"]), weapon=str(c["weapon"]), room=str(c["room"]), disprover=disprover, shown_card=shown)
                )
            elif self._flow_kind == "fact":
                self.session.observations.append(FactObservation(player=str(c["player"]), card=str(c["card"]), has=c["has"] == "holds the card"))
            elif self._flow_kind == "rename":
                card, label = str(c["card"]), str(c.get("label", "")).strip()
                if not label or label == card:
                    self.session.card_names.pop(card, None)
                else:
                    self.session.card_names[card] = label
        finally:
            self._flow_kind, self._step, self._flow = "", None, []
            self.query_one("#entry_title", Static).update("[dim]s = add suggestion   f = add fact   u = undo   n = rename card   e = edit setup[/dim]")
            self.query_one("#entry_choices", OptionList).clear_options()
            self.query_one("#entry_multi", SelectionList).clear_options()
            self.query_one("#entry_input", Input).display = False
            self.query_one("#entry_multi", SelectionList).display = False
        self.recompute()

    def _observation_valid(self, ob: SuggestionObservation | FactObservation) -> bool:
        names = set(self.session.players)
        if isinstance(ob, FactObservation):
            return ob.player in names
        return ob.suggester in names and (ob.disprover is None or ob.disprover in names)

    def _advance(self, value: Any) -> None:
        if self._step is None:
            return
        self._collect[str(self._step["key"])] = value
        self._next_step()

    @on(OptionList.OptionSelected, "#entry_choices")
    def _picked(self, ev: OptionList.OptionSelected) -> None:
        if self._step is not None and self._step["kind"] == "pick":
            self._advance(self._step["resolved"][ev.option_index])

    @on(Input.Submitted, "#entry_input")
    def _typed(self, ev: Input.Submitted) -> None:
        if self._step is not None and self._step["kind"] == "input":
            self._advance(self._input_value(ev.value))

    def _input_value(self, raw: str) -> Any:
        """Input steps: the rename label is a raw string; the players step is a comma list."""
        if self._step is not None and self._step["key"] == "label":
            return raw.strip()
        return [n.strip() for n in raw.split(",") if n.strip()]

    @on(Button.Pressed, "#b_confirm")
    def _confirm(self) -> None:
        if self._step is None:
            return
        if self._step["kind"] == "multi":
            self._advance(list(self.query_one("#entry_multi", SelectionList).selected))
        elif self._step["kind"] == "pick":
            ol = self.query_one("#entry_choices", OptionList)
            if ol.highlighted is not None:
                self._advance(self._step["resolved"][ol.highlighted])
        else:
            inp = self.query_one("#entry_input", Input)
            self._advance(self._input_value(inp.value))

    @on(Button.Pressed, "#b_back")
    def action_cancel(self) -> None:
        if self._flow_kind:
            self._flow_kind, self._step, self._flow = "", None, []
            self.query_one("#entry_title", Static).update("[dim]cancelled[/dim]")
            self.query_one("#entry_choices", OptionList).clear_options()
            self.query_one("#entry_multi", SelectionList).display = False
            self.query_one("#entry_input", Input).display = False

    def action_undo(self) -> None:
        if self.session.observations:
            dropped = self.session.observations.pop()
            self._status(f"removed: {observation_label(dropped, self.session.card_names)}")
            self.recompute()

    def action_save(self) -> None:
        path = self.path or "analyst_session.json"
        Path(path).write_text(json.dumps(self.session.model_dump(), indent=1), encoding="utf-8")
        self.path = path
        self._status(f"session saved to {path}")

    def action_quit_app(self) -> None:
        self.exit()

    # ---------------- analysis + rendering
    def recompute(self) -> None:
        self.report = analyze(self.session, accuse_threshold=self.threshold) if self.session.players else None
        self._render_session()
        self._render_observations()
        self._render_report()
        if self.path:
            Path(self.path).write_text(json.dumps(self.session.model_dump(), indent=1), encoding="utf-8")

    def _render_session(self) -> None:
        s = self.session
        ed = edition_def(s.edition).label if s.edition in EDITIONS else s.edition
        lines = [
            f"[b]{ed}[/b] - {len(s.players)} players: " + ", ".join(f"[b]{p}[/b]" if p == s.me else p for p in s.players),
            f"your hand ({len(s.my_cards)}): " + (", ".join(self._lab(c) for c in s.my_cards) or "[dim]none entered[/dim]"),
        ]
        if s.faceup:
            lines.append("face-up: " + ", ".join(self._lab(c) for c in s.faceup))
        if s.card_names:
            lines.append(f"[dim]{len(s.card_names)} card(s) renamed (n to rename)[/dim]")
        self.query_one("#session", Static).update("\n".join(lines) if s.players else "[dim]press e to set up the session[/dim]")

    def _render_observations(self) -> None:
        ol = self.query_one("#observations", OptionList)
        ol.clear_options()
        ol.add_options([Option(f"{i}. {observation_label(ob, self.session.card_names)}") for i, ob in enumerate(self.session.observations, 1)])

    def _render_report(self) -> None:
        table = self.query_one("#probs", DataTable)
        cand = self.query_one("#candidates", Static)
        guide = self.query_one("#guide", Static)
        table.clear(columns=True)
        r = self.report
        if r is None:
            cand.update("")
            guide.update("[dim]enter your session to see the analysis[/dim]")
            return
        if not r["ok"]:
            cand.update("")
            guide.update("[red]Session problems:[/red]\n" + "\n".join(f" - {e}" for e in r["errors"]))
            self._status("fix the session to see the analysis (e = edit setup, u = undo)")
            return
        ed, players = self.session.edition, self.session.players
        table.add_column("Card", key="card")
        table.add_column("Env", key="env")
        for p in players:
            table.add_column(p[:8], key=p)
        env_probs: dict[str, float] = r["solution"]["cards"]
        holders: dict[str, dict[str, float]] = r["holders"]

        def cell(card: str, holder: str) -> str:
            pr = holders.get(card, {}).get(holder, 0.0)
            if pr >= 0.9995:
                return "[green]X[/green]"
            return f"{100 * pr:.0f}" if pr > 0.0005 else "[dim].[/dim]"

        for group, cards in (("suspects", suspects(ed)), ("weapons", weapons(ed)), ("rooms", rooms(ed))):
            table.add_row(f"[b]{group.upper()}[/b]", *[""] * (len(players) + 1))
            for card in cards:
                env = env_probs.get(card, 0.0)
                env_cell = f"[b yellow]{100 * env:.0f}[/b yellow]" if env >= 0.5 else (f"{100 * env:.0f}" if env > 0.0005 else "[dim].[/dim]")
                table.add_row(self._lab(card), env_cell, *[cell(card, p) for p in players])
        sol = r["solution"]
        mark = "" if sol["exact"] else " [dim](estimated)[/dim]"
        top = "\n".join(f"  {100 * p:5.1f}%  {' | '.join(self._lab(c) for c in combo.split(' | '))}" for combo, p in list(sol["combos"].items())[:6])
        cand.update(f"[b]{sol['n_possible']}[/b] candidate(s){mark}\n{top}" if sol["n_possible"] else "[red]no consistent solution - an observation must be wrong[/red]")
        g = r["guide"]
        lines = [f"[b]{line}[/b]" if i == 0 else line for i, line in enumerate(g["advice"])]
        if r["deductions"]:
            lines.append("\n[b]Hard deductions[/b] (provable facts):")
            lines.extend(f" - {d}" for d in r["deductions"][:8])
        if g["suggestions"]:
            lines.append("\n[b]Best suggestions to make next[/b]:")
            lines.extend(f" - {self._lab(t['suspect'])} + {self._lab(t['weapon'])} in {self._lab(t['room'])}  (score {t['score']:.2f})" for t in g["suggestions"])
        th = r["threat"]
        if th["opponents"]:
            lines.append("\n[b]Opponent threat[/b]:")
            lines.extend(f" - {p}: ~{d['n_possible']} candidates left, p(win next) {d['p_win_next_turn']:.2f}" for p, d in th["opponents"].items())
        guide.update("\n".join(lines))
        self._status(f"{len(self.session.observations)} observation(s) - s suggestion, f fact, n rename, u undo, ctrl+s save, q quit")

    def _status(self, msg: str) -> None:
        self.query_one("#status", Static).update(msg)


def run_analyst(session: AnalysisSession | None = None, path: str | None = None, threshold: float = 0.9) -> None:
    AnalystApp(session, path, threshold).run()

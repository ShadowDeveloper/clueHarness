"""Textual TUI: board, notebook, event log and a guided action panel.

The game loop (`run_game`) runs in a worker thread. The human seat is a `TUIHumanAgent` whose
`choose_action` / `choose_card_to_show` post a request to the app and block on a queue until the
user confirms a choice. AI seats run untouched. Spectator mode streams events at a set pace.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from clue.agents.base import PlayerAgent
from clue.agents.human import describe_event
from clue.manager import GameManager
from clue.manager.runner import GameInterrupted
from clue.rules import Action
from clue.rules import board as B
from clue.rules.cards import ROOMS, WEAPONS
from clue.tui.board_render import render_board, token_glyph


# --------------------------------------------------------------------------- agent <-> UI bridge
@dataclass
class Request:
    kind: str  # "action" | "card"
    observation: dict[str, Any]
    legal: list[Action] = field(default_factory=list)
    cards: list[str] = field(default_factory=list)
    reply: queue.Queue[Any] = field(default_factory=queue.Queue)


class TUIHumanAgent(PlayerAgent):
    """Human seat whose decisions come from the Textual app."""

    kind = "human"

    def __init__(self, player_id: str) -> None:
        super().__init__(player_id)
        self.app: ClueApp | None = None

    def _ask(self, req: Request) -> Any:
        assert self.app is not None
        self.app.call_from_thread(self.app.show_request, req)
        ans = req.reply.get()
        if ans is None:  # the app is quitting: abandon this decision, the runner leaves the game resumable
            raise GameInterrupted()
        return ans

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        act = self._ask(Request("action", observation, legal=legal_actions))
        assert isinstance(act, Action)
        return act

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        if len(cards_that_can_disprove) == 1:
            return cards_that_can_disprove[0]
        return str(self._ask(Request("card", observation, cards=cards_that_can_disprove)))


# --------------------------------------------------------------------------- widgets
class NotebookView(DataTable[str]):
    def refresh_from(self, obs: dict[str, Any]) -> None:
        self.clear(columns=True)
        players = [p["id"] for p in obs["board"]["players"]]
        self.add_columns("Card", *players, "")
        nb = obs["notebook"]
        me = obs["you"]["id"]
        for cat in ("suspects", "weapons", "rooms"):
            for c in obs["cards"][cat]:
                holder = nb["known_holder"].get(c)
                row = []
                for p in players:
                    if holder == p:
                        row.append("[green]✔[/]")
                    elif holder:
                        row.append("[dim]·[/]")
                    elif c in nb["not_held"].get(p, []):
                        row.append("[red]✘[/]")
                    else:
                        row.append("[dim]?[/]")
                if c in obs["you"]["hand"]:
                    status = "[green]yours[/]"
                elif holder:
                    status = f"[yellow]{holder} has it[/]"
                elif c in nb["faceup"]:
                    status = "face-up"
                elif all(c in nb["not_held"].get(p, []) for p in players if p != me):
                    status = "[bold red]ENVELOPE![/]"
                else:
                    status = ""
                self.add_row(c, *row, status, key=f"{me}:{c}")


class OmniscientView(DataTable[str]):
    """Spectator table: the TRUE holder of every card (hands, face-up, envelope) plus what each seat has deduced."""

    def refresh_from(self, gm: GameManager) -> None:
        self.clear(columns=True)
        st = gm.state
        players = [p.id for p in st.players]
        self.add_columns("Card", "Truth", *[f"{p} knows" for p in players])
        holder = {c: p.id for p in st.players for c in p.hand}
        for c in st.faceup:
            holder[c] = "face-up"
        for c in st.solution:
            holder[c] = "ENVELOPE"
        from clue.rules.cards import ROOMS, WEAPONS, suspects

        for cat in (list(suspects(st.config.edition)), list(WEAPONS), list(ROOMS)):
            for c in cat:
                truth = holder.get(c, "?")
                tcell = "[bold red]ENVELOPE[/]" if truth == "ENVELOPE" else ("[dim]face-up[/]" if truth == "face-up" else f"[green]{truth}[/]")
                row = []
                for p in players:
                    nb = gm.notebooks[p]
                    if c in nb.my_hand:
                        row.append("[green]mine[/]")
                    elif c in nb.known_holder:
                        row.append(f"[yellow]{nb.known_holder[c]}[/]")
                    elif all(c in nb.not_held.get(q, []) for q in players if q != p):
                        row.append("[bold red]env![/]")
                    else:
                        n_out = sum(1 for q in players if q != p and c in nb.not_held.get(q, []))
                        row.append(f"[dim]?{'✘' * n_out}[/]" if n_out else "[dim]?[/]")
                self.add_row(c, tcell, *row, key=f"omni:{c}")


# --------------------------------------------------------------------------- app
class ClueApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #top { height: 1fr; }
    #board { width: 56; height: 100%; border: round $accent; padding: 0 1; }
    #middle { width: 1fr; min-width: 50; }
    #notebook { height: 1fr; border: round $secondary; }
    #omni { height: 1fr; border: round $secondary; display: none; }
    #facts { height: auto; max-height: 9; border: round $secondary; padding: 0 1; }
    #coach { height: auto; max-height: 10; border: round $success; padding: 0 1; display: none; }
    #right { width: 60; }
    #log { height: 1fr; min-height: 8; border: round $primary; }
    #panel { height: auto; max-height: 60%; border: heavy $warning; padding: 0 1; }
    #banner { height: auto; text-style: bold; padding: 0 0 1 0; }
    #buttons { height: auto; }
    #buttons Button { min-width: 9; margin: 0 1 0 0; }
    #picker { height: auto; max-height: 16; display: none; }
    #picker_title { height: auto; color: $text-muted; }
    #choices { height: auto; max-height: 12; }
    #confirm_row { height: auto; }
    #status { height: 1; background: $boost; padding: 0 1; }
    """
    BINDINGS = [
        Binding("r", "roll", "Roll"),
        Binding("p", "passage", "Passage"),
        Binding("s", "suggest", "Suggest"),
        Binding("a", "accuse", "Accuse"),
        Binding("e", "end_turn", "End turn"),
        Binding("escape", "cancel", "Back"),
        Binding("space", "pause", "Pause"),
        Binding("plus", "faster", "Faster"),
        Binding("minus", "slower", "Slower"),
        Binding("h", "coach", "Coach"),
        Binding("v", "cycle_viewer", "Viewer"),
        Binding("ctrl+s", "save", "Save"),
        Binding("q", "quit_game", "Quit"),
    ]

    def __init__(self, gm: GameManager, agents: dict[str, PlayerAgent], delay: float = 0.6, emoji: bool = True, ponder: bool = False, ponder_grace: float = 2.0, autosave: str | None = None) -> None:
        super().__init__()
        self.autosave = autosave  # checkpoint path rewritten after every action (None = off)
        self._stop = False  # set by q: the game loop exits at the next safe point and the app closes
        self.emoji = emoji
        self.ponder = ponder
        self.ponder_grace = ponder_grace
        self.gm = gm
        self.agents = agents
        self.human = next((a for a in agents.values() if isinstance(a, TUIHumanAgent)), None)
        # spectating: omniscient by default (viewer=None -> everything visible); `v` cycles through seat perspectives
        self.viewer: str | None = self.human.id if self.human else None
        self.delay = delay
        self.paused = False
        self.req: Request | None = None
        self.mode = "idle"  # idle | main | move | pick | card
        self._build: dict[str, str | None] = {}
        self._build_kind = ""
        self._pick_fields: list[str] = []
        self._selected: str | None = None
        self.coach = False  # coach mode: on-demand exact-solver hints for the human viewer (never auto-shown)
        self._coach_used = 0

    # ---------------- layout
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="top"):
            yield Static(id="board")
            with Vertical(id="middle"):
                yield NotebookView(id="notebook", zebra_stripes=True, cursor_type="none")
                yield OmniscientView(id="omni", zebra_stripes=True, cursor_type="none")
                yield Static(id="facts")
                yield Static(id="coach")
            with Vertical(id="right"):
                yield RichLog(id="log", wrap=True, markup=True, highlight=False, min_width=20)
                with Vertical(id="panel"):
                    yield Static("", id="banner")
                    with Horizontal(id="buttons"):
                        yield Button("Roll (r)", id="b_roll", variant="primary")
                        yield Button("Passage (p)", id="b_passage")
                        yield Button("Suggest (s)", id="b_suggest", variant="success")
                        yield Button("Accuse (a)", id="b_accuse", variant="error")
                        yield Button("End turn (e)", id="b_end")
                    with VerticalScroll(id="picker"):
                        yield Static("", id="picker_title")
                        yield OptionList(id="choices")
                        with Horizontal(id="confirm_row"):
                            yield Button("Confirm", id="b_confirm", variant="primary")
                            yield Button("Back (esc)", id="b_back")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Clue"
        self.sub_title = "  ".join(f"{s.id}: {s.label()}" for s in self.gm.specs)
        if self.human:
            self.human.app = self
        self.query_one("#board", Static).border_title = "Board"
        self.query_one("#notebook", NotebookView).border_title = "Notebook  ✔ has  ✘ hasn't  ? unknown"
        self.query_one("#facts", Static).border_title = "Deductions"
        self.query_one("#log", RichLog).border_title = "What happened"
        self.query_one("#panel", Vertical).border_title = "Your move"
        self._set_buttons(set())
        self._set_banner("[dim]Waiting for the game to start…[/]")
        self.refresh_view()
        self.run_worker(self._game_loop, thread=True, exclusive=True)

    # ---------------- game loop (worker thread)
    def _game_loop(self) -> None:
        import time

        from clue.manager.runner import run_game

        def on_events(_gm: GameManager, _evs: list[dict[str, Any]]) -> None:
            evs = [e.redacted_for(self.viewer) if self.viewer is not None else {"type": e.type, "turn": e.turn, "player": e.player, **e.public, **e.private} for e in _gm.events[-len(_evs) :]]
            self.call_from_thread(self._on_events, evs)
            if self.human is None or _gm.acting_player() != self.viewer:
                while self.paused:
                    time.sleep(0.1)
                time.sleep(self.delay)

        try:
            run_game(self.gm, self.agents, on_events, ponder=self.ponder, ponder_grace=self.ponder_grace, autosave=self.autosave, stop=lambda: self._stop)
        except Exception as e:
            self.call_from_thread(self.log_line, f"[red]error: {e}[/]")
        if self._stop and not self.gm.finished:
            self.call_from_thread(self.exit)
            return
        self.call_from_thread(self._finish, self.gm.summary())

    def _on_events(self, evs: list[dict[str, Any]]) -> None:
        for e in evs:
            style = ""
            t = e["type"]
            if t in ("accuse", "game_over", "eliminated"):
                style = "bold red"
            elif t == "no_one_disproved":
                style = "bold yellow"
            elif t == "turn_start":
                style = "bold cyan"
            elif t == "disproved" and "card" in e:
                style = "bold green"
            elif t == "suggest":
                style = "bold"
            line = describe_event(e)
            if t == "turn_start" and e.get("player") == self.viewer and self.human is not None:
                line = "━━━ YOUR TURN ━━━"
            self.log_line(f"[{style}]{line}[/]" if style else line)
        self.refresh_view()

    def _finish(self, s: dict[str, Any]) -> None:
        self.mode = "idle"
        self._set_buttons(set())
        self._show_picker(False)
        who = "You win! 🎉" if (self.human and s["winner"] == self.viewer) else f"{s['winner']} wins." if s["winner"] else "Nobody solved it."
        self._set_banner(f"[bold]GAME OVER — {who}[/]\nSolution: {s['solution'][0]} · {s['solution'][1]} · {s['solution'][2]}\nPress q to quit.")
        self.query_one("#status", Static).update(f"finished after {s['turns']} turns · replay hash {self.gm.replay_hash()[:16]}")

    # ---------------- rendering helpers
    def log_line(self, text: str) -> None:
        self.query_one("#log", RichLog).write(text)

    def _set_banner(self, text: str) -> None:
        self.query_one("#banner", Static).update(text)

    def _set_buttons(self, enabled: set[str]) -> None:
        for bid in ("b_roll", "b_passage", "b_suggest", "b_accuse", "b_end"):
            btn = self.query_one(f"#{bid}", Button)
            btn.disabled = bid not in enabled
            btn.display = bid in enabled
        self.query_one("#buttons", Horizontal).display = bool(enabled)

    def _show_picker(self, show: bool, title: str = "") -> None:
        self.query_one("#picker", VerticalScroll).display = show
        self.query_one("#picker_title", Static).update(title)
        if show:
            self.query_one("#choices", OptionList).focus()

    def _view_id(self) -> str:
        """Seat whose observation drives the panels: the human, the chosen spectator seat, or (omniscient) the acting player."""
        if self.viewer is not None:
            return self.viewer
        try:
            return self.gm.acting_player()
        except Exception:
            return self.gm.player_ids()[0]

    def refresh_view(self) -> None:
        vid = self._view_id()
        omni = self.human is None and self.viewer is None
        obs = self.gm.get_observation(vid)
        hl = set(obs["board"]["your_legal_moves"]) if self.mode == "move" or obs["turn"]["roll"] else set()
        self.query_one("#board", Static).update(render_board(obs["board"]["token_positions"], obs["cards"]["suspects"], hl, obs["board"]["weapon_positions"], obs["you"]["suspect_token"], self.emoji))
        nbv, ov = self.query_one("#notebook", NotebookView), self.query_one("#omni", OmniscientView)
        nbv.display, ov.display = not omni, omni
        if omni:
            ov.refresh_from(self.gm)
            ov.border_title = "All hands (omniscient) — v to view one seat"
        else:
            nbv.refresh_from(obs)
            nbv.border_title = f"Notebook of {vid}" if self.human is None else "Notebook"
        nb = obs["notebook"]
        facts = []
        for c in nb["has_one_of"][-4:]:
            facts.append(f"• {c['player']} holds at least one of {', '.join(c['cards'])}")
        for c in nb["unrefuted_suggestions"][-3:]:
            facts.append(f"• [yellow]nobody could disprove[/] {', '.join(c['cards'])} (suggested by {c['player']})")
        for n in nb["notes"][-2:]:
            facts.append(f"• [dim]note:[/] {n}")
        facts_w = self.query_one("#facts", Static)
        facts_w.border_title = f"Deductions of {vid}" if self.human is None else "Deductions"
        facts_w.update("\n".join(facts) or "[dim]Nothing deduced yet. Make suggestions to learn who holds what.[/]")
        coach = self.query_one("#coach", Static)
        coach.display = self.coach
        if self.coach:
            coach.border_title = "Coach (h to hide)"
            coach.update(self._coach_text(obs))
        you = obs["you"]
        pos = you["position"] if B.is_room(you["position"]) else f"corridor {you['position']}"
        glyph = token_glyph("SMWGKP"[obs["cards"]["suspects"].index(you["suspect_token"])], self.emoji).strip()
        st = f"You are {glyph} {you['suspect_token']} ({you['id']}) in the {pos}   ·   your cards: {', '.join(you['hand'])}   ·   turn {obs['turn']['number']}"
        if self.human is None:
            sol = " · ".join(self.gm.state.solution)
            seat = f"{glyph} {you['suspect_token']} ({you['id']}) in the {pos} · hand: {', '.join(you['hand'])}"
            view = f"omniscient · envelope: [bold red]{sol}[/] · now playing {seat}" if omni else f"viewing as {seat}"
            st = f"Spectating {'⏸ paused' if self.paused else '▶'} {self.delay:.1f}s/event · turn {obs['turn']['number']} · {view}"
        if self.ponder:
            thinking = [pid for pid, ps in self.gm.ponder_stats.items() if ps.get("sessions")] if self.gm.finished else self._thinking_now()
            if thinking:
                st += "   ·   💭 thinking: " + ", ".join(thinking)
        self.query_one("#status", Static).update(st)

    def _thinking_now(self) -> list[str]:
        pm = getattr(self.gm, "_ponder_manager", None)
        if pm is None:
            return []
        return [pid for pid, sess in pm.sessions.items() if sess.thread.is_alive() and not sess.ctx.stopped]

    # ---------------- requests from the human agent
    def show_request(self, req: Request) -> None:
        self.req = req
        self._build = {}
        self._selected = None
        self.refresh_view()
        if req.kind == "card":
            self.mode = "card"
            ps = req.observation["turn"]["pending_suggestion"]
            self._set_buttons(set())
            head = f"{ps['suggester']} suggested [bold]{ps['suspect']}[/] with the [bold]{ps['weapon']}[/] in the [bold]{ps['room']}[/]."
            self._set_banner(head + f"\nYou hold more than one of these — choose which card to show {ps['suggester']}:")
            self._fill_choices([(c, c) for c in req.cards])
            self._show_picker(True, "Only the suggester will see it.")
        else:
            self._main_menu()
        self.bell()

    def _main_menu(self) -> None:
        assert self.req is not None
        self.mode = "main"
        obs = self.req.observation
        types = {a.type for a in self.req.legal}
        enabled: set[str] = set()
        lines = []
        if "roll" in types:
            enabled.add("b_roll")
            lines.append("Roll the dice and move")
        if "passage" in types:
            enabled.add("b_passage")
            lines.append(f"Take the secret passage to the {B.SECRET_PASSAGES[obs['you']['position']]}")
        if "move" in types:
            self._move_menu()
            return
        if "suggest" in types:
            enabled.add("b_suggest")
            lines.append(f"Suggest here in the {obs['you']['position']}" + (" (you were brought here — no need to move)" if "roll" in types else ""))
        if obs["can_accuse"]:
            enabled.add("b_accuse")
        if "end_turn" in types:
            enabled.add("b_end")
            lines.append("End your turn")
        self._set_buttons(enabled)
        self._show_picker(False)
        head = "[bold]It's your turn.[/]\n" if "roll" in types else ""
        body = "\n".join(f"• {ln}" for ln in lines) if lines else "• Choose an action"
        self._set_banner(head + body + "\n[dim]Accuse only when sure — a wrong accusation eliminates you.[/]")

    def _move_menu(self) -> None:
        assert self.req is not None
        self.mode = "move"
        obs = self.req.observation
        self._set_buttons({"b_accuse"} if obs["can_accuse"] else set())
        rooms = [a for a in self.req.legal if a.type == "move" and B.is_room(a.to or "")]
        cells = [a for a in self.req.legal if a.type == "move" and not B.is_room(a.to or "")]
        opts: list[tuple[str, str]] = []
        for a in rooms:
            opts.append((f"move:{a.to}", f"Enter the {a.to}  (you can suggest there)"))
        for a in cells:
            opts.append((f"move:{a.to}", f"Corridor square {a.to}"))
        self._fill_choices(opts)
        self._set_banner(f"You rolled [bold]{obs['turn']['roll']}[/]. Where do you want to go?  (◆ on the board = reachable)")
        self._show_picker(True, f"{len(rooms)} room(s) and {len(cells)} corridor square(s) in reach")
        self.refresh_view()

    def _start_build(self, kind: str) -> None:
        assert self.req is not None
        obs = self.req.observation
        self._build_kind = kind
        self._build = {"suspect": None, "weapon": None, "room": obs["you"]["position"] if kind == "suggest" else None}
        self._pick_fields = ["suspect", "weapon"] + (["room"] if kind == "accuse" else [])
        self._pick_next()

    def _pick_next(self) -> None:
        assert self.req is not None
        self.mode = "pick"
        self._set_buttons(set())
        obs = self.req.observation
        remaining = [f for f in self._pick_fields if self._build.get(f) is None]
        if not remaining:
            act = Action(type=self._build_kind, player=self._view_id(), **self._build)  # type: ignore[arg-type]
            self._reply(act)
            return
        fname = remaining[0]
        pool = {"suspect": obs["cards"]["suspects"], "weapon": list(WEAPONS), "room": list(ROOMS)}[fname]
        hand = set(obs["you"]["hand"])
        known = set(obs["notebook"]["known_holder"]) - hand
        opts = []
        for c in pool:
            tag = "  [green](your card)[/]" if c in hand else "  [yellow](seen — not in envelope)[/]" if c in known else ""
            opts.append((f"pick:{fname}:{c}", c + tag))
        self._fill_choices(opts)
        chosen = " · ".join(str(self._build[f]) for f in ("suspect", "weapon", "room") if self._build.get(f))
        verb = "SUGGEST" if self._build_kind == "suggest" else "ACCUSE"
        self._set_banner(f"[bold]{verb}[/]  {chosen or ''}\nStep {len(self._pick_fields) - len(remaining) + 1} of {len(self._pick_fields)}: choose the {fname}")
        self._show_picker(True, "Enter or Confirm to pick · Esc to go back")

    def _fill_choices(self, opts: list[tuple[str, str]]) -> None:
        ol = self.query_one("#choices", OptionList)
        ol.clear_options()
        for oid, label in opts:
            ol.add_option(Option(label, id=oid))
        if opts:
            ol.highlighted = 0
            self._selected = opts[0][0]

    def _reply(self, value: Any) -> None:
        assert self.req is not None
        req, self.req = self.req, None
        self.mode = "idle"
        self._set_buttons(set())
        self._show_picker(False)
        self._set_banner("[dim]Waiting for the other players…[/]")
        req.reply.put(value)

    def _commit(self, oid: str) -> None:
        if self.req is None:
            return
        if oid.startswith("move:"):
            act = next(a for a in self.req.legal if a.type == "move" and a.to == oid[5:])
            self._reply(act)
        elif oid.startswith("pick:"):
            _, fname, value = oid.split(":", 2)
            self._build[fname] = value
            self._pick_next()
        elif self.mode == "card":
            self._reply(oid)

    # ---------------- events
    @on(OptionList.OptionHighlighted, "#choices")
    def _highlighted(self, ev: OptionList.OptionHighlighted) -> None:
        self._selected = str(ev.option.id)

    @on(OptionList.OptionSelected, "#choices")
    def _selected_opt(self, ev: OptionList.OptionSelected) -> None:
        self._commit(str(ev.option.id))

    @on(Button.Pressed)
    def _button(self, ev: Button.Pressed) -> None:
        bid = ev.button.id
        if bid == "b_confirm":
            if self._selected:
                self._commit(self._selected)
        elif bid == "b_back":
            self.action_cancel()
        elif bid == "b_roll":
            self.action_roll()
        elif bid == "b_passage":
            self.action_passage()
        elif bid == "b_suggest":
            self.action_suggest()
        elif bid == "b_accuse":
            self.action_accuse()
        elif bid == "b_end":
            self.action_end_turn()

    def _simple(self, atype: str) -> None:
        if self.req and self.mode in ("main", "move"):
            act = next((a for a in self.req.legal if a.type == atype), None)
            if act:
                self._reply(act)

    def action_roll(self) -> None:
        self._simple("roll")

    def action_passage(self) -> None:
        self._simple("passage")

    def action_end_turn(self) -> None:
        self._simple("end_turn")

    def action_suggest(self) -> None:
        if self.req and self.mode == "main" and any(a.type == "suggest" for a in self.req.legal):
            self._start_build("suggest")

    def action_accuse(self) -> None:
        if self.req and self.mode in ("main", "move") and self.req.observation["can_accuse"]:
            self._start_build("accuse")

    def action_cancel(self) -> None:
        if self.req is None:
            return
        if self.mode == "pick":
            done = [f for f in self._pick_fields if self._build.get(f) is not None]
            if done:
                self._build[done[-1]] = None
                self._pick_next()
            else:
                self._main_menu()
        elif self.mode == "card":
            return  # must choose
        else:
            self._main_menu()

    def action_coach(self) -> None:
        """Toggle coach mode. Hints are computed from the viewer's own notebook only and are never persisted."""
        self.coach = not self.coach
        if self.coach:
            self._coach_used += 1
            self.gm.log_agent_note(self._view_id(), {"summary": "coach_mode_on", "count": self._coach_used})
        self.refresh_view()

    def _coach_text(self, obs: dict[str, Any]) -> str:
        from clue.tools.coach import coach_hints

        req = self.req if (self.req is not None and self.req.kind != "card") else None
        h = coach_hints(self.gm, self._view_id(), obs, req.legal if req else None)
        lines = [f"[bold]{h['candidates']}[/] envelope combination(s) still possible"]
        if h["most_likely"]:
            m = h["most_likely"]
            lines.append(f"most likely: {m['suspect']} · {m['weapon']} · {m['room']} ({m['p']:.0%})")
        lines += [f"[green]✓[/] {d}" for d in h["deductions"]]
        if h["expert_action"]:
            lines.append(f"[cyan]expert would:[/] {h['expert_action']['key']}")
        elif h["error"]:
            lines.append(f"[dim]no recommendation ({h['error']})[/]")
        return "\n".join(lines)

    def action_save(self) -> None:
        """Manual checkpoint (ctrl+s). Uses the autosave path or saves/game_<seed>.json."""
        path = self.autosave or f"saves/game_{self.gm.seed}.json"
        try:
            p = self.gm.save(path, self.agents)
            self.log_line(f"[green]saved to {p} — resume with: clue play --resume {p}[/]")
        except Exception as e:
            self.log_line(f"[red]save failed: {e}[/]")

    def action_quit_game(self) -> None:
        """q: if the game is over just quit; otherwise checkpoint, stop the loop at the next safe point and exit."""
        if self.gm.finished or self._stop:
            self.exit()
            return
        self._stop = True
        self.paused = False
        path = self.autosave or f"saves/game_{self.gm.seed}.json"
        try:
            self.gm.save(path, self.agents)
            self.autosave = path
        except Exception as e:  # still let the user leave
            self.log_line(f"[red]save failed: {e}[/]")
        self._set_banner(f"[bold]Saving and quitting…[/]\nResume with: clue play --resume {path}")
        # a pending human request would block the loop forever: answer it with a no-op signal
        if self.req is not None:
            req, self.req = self.req, None
            req.reply.put(None)
            self.mode = "idle"
            self._set_buttons(set())
            self._show_picker(False)
        self.set_timer(3.0, self.exit)  # safety net if the loop is stuck inside a slow (LLM) decision

    def action_cycle_viewer(self) -> None:
        """Spectators only: omniscient -> P1 -> P2 ... -> omniscient. (The event log keeps past lines as they were shown.)"""
        if self.human is not None:
            return
        ids = self.gm.player_ids()
        if self.viewer is None:
            self.viewer = ids[0]
        else:
            i = ids.index(self.viewer) + 1
            self.viewer = ids[i] if i < len(ids) else None
        self.log_line(f"[dim]— view: {self.viewer or 'omniscient'} —[/]")
        self.refresh_view()

    def action_pause(self) -> None:
        self.paused = not self.paused
        self.refresh_view()

    def action_faster(self) -> None:
        self.delay = max(0.0, self.delay - 0.2)
        self.refresh_view()

    def action_slower(self) -> None:
        self.delay += 0.2
        self.refresh_view()


def run_tui(gm: GameManager, agents: dict[str, PlayerAgent], delay: float = 0.6, emoji: bool = True, ponder: bool = False, ponder_grace: float = 2.0, autosave: str | None = None) -> GameManager:
    """Blocking: run the Textual app until the game ends (or the user quits; the game is then checkpointed)."""
    ClueApp(gm, agents, delay=delay, emoji=emoji, ponder=ponder, ponder_grace=ponder_grace, autosave=autosave).run()
    return gm

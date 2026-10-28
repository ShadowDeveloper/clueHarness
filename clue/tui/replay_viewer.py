"""TUI replay viewer: step through a replay (.jsonl/.json) with the board reconstructed from public events.

Keys: → / n next event, ← / b previous, space autoplay, + / - speed, g / G start / end, v cycle viewer redaction, q quit.
Only public information plus the selected viewer's private fields are shown (same redaction as the manager).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, RichLog, Static

from clue.agents.human import describe_event
from clue.replay.state import ReplayState, load_replay
from clue.rules import board as B
from clue.tui.board_render import render_board


class ReplayApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #top { height: 1fr; }
    #board { width: 56; height: 100%; border: round $accent; padding: 0 1; scrollbar-size: 1 1; }
    #board_content { height: auto; }
    #side { width: 1fr; min-width: 24; }
    #info { height: auto; border: round $secondary; padding: 0 1; }
    #log { height: 1fr; border: round $primary; }
    #status { height: 1; background: $boost; padding: 0 1; }
    """
    BINDINGS = [
        Binding("right,n", "next", "Next"),
        Binding("left,b", "prev", "Prev"),
        Binding("space", "autoplay", "Play/Pause"),
        Binding("plus", "faster", "Faster"),
        Binding("minus", "slower", "Slower"),
        Binding("home,g", "first", "Start"),
        Binding("end,G", "last", "End"),
        Binding("v", "cycle_viewer", "Viewer"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, records: list[dict[str, Any]], emoji: bool = True, delay: float = 0.5) -> None:
        super().__init__()
        self.rs = ReplayState(records)
        self.emoji = emoji
        self.delay = delay
        self.playing = False
        self.viewer_idx = -1  # -1 = omniscient
        self.position = 0  # index in the current viewer's visible event stream
        self._board_content_width = 4 + 2 * B.board_for(self.rs.edition).cols
        self._board_content_height = 0

    @property
    def viewer(self) -> str | None:
        return None if self.viewer_idx < 0 else str(self.rs.players[self.viewer_idx]["id"])

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="top"):
            with ScrollableContainer(id="board"):
                yield Static(id="board_content")
            with Vertical(id="side"):
                yield Static(id="info")
                yield RichLog(id="log", wrap=True, markup=True, highlight=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Clue replay"
        self.query_one("#board", ScrollableContainer).border_title = "Board"
        self.query_one("#log", RichLog).border_title = "Events"
        self.query_one("#info", Static).border_title = "Game"
        self.render_all()
        self.set_interval(0.1, self._tick)

    def on_resize(self, event: events.Resize) -> None:
        self._fit_board(event.size.width, event.size.height)

    def _fit_board(self, screen_width: int | None = None, screen_height: int | None = None) -> None:
        if not self.query("#board_content"):
            return
        screen_width = self.size.width if screen_width is None else screen_width
        screen_height = self.size.height if screen_height is None else screen_height
        needs_vertical_scrollbar = self._board_content_height > max(0, screen_height - 5)
        natural_width = self._board_content_width + 4 + int(needs_vertical_scrollbar)
        available = max(24, screen_width - 40)
        self.query_one("#board", ScrollableContainer).styles.width = min(natural_width, available)

    def _tick(self) -> None:
        if not self.playing:
            return
        self._acc = getattr(self, "_acc", 0.0) + 0.1
        if self._acc >= self.delay:
            self._acc = 0.0
            if self.position >= len(self.rs.visible_event_indices(self.viewer)):
                self.playing = False
                self.render_all()
            else:
                self.action_next()

    def _redact(self, ev: dict[str, Any]) -> dict[str, Any] | None:
        return self.rs.redact_event(ev, self.viewer)

    def render_all(self) -> None:
        rs = self.rs
        me = rs.seat.get(self.viewer or "", rs.suspects[0])
        hl: set[str] = set()
        if rs.last_suggestion and rs.idx and rs.events[rs.idx - 1] is rs.last_suggestion:
            hl = {str(rs.last_suggestion["room"])}
        board_txt = render_board(rs.tokens, rs.suspects, hl, rs.weapons, me, self.emoji, rs.edition)
        board_content = self.query_one("#board_content", Static)
        self._board_content_height = len(board_txt.plain.splitlines())
        board_content.styles.width = self._board_content_width
        board_content.styles.height = self._board_content_height
        board_content.update(board_txt)
        self._fit_board()
        log = self.query_one("#log", RichLog)
        log.clear()
        visible_history = [ev for ev in rs.events[: rs.idx] if rs.event_visible(ev, self.viewer)]
        for ev in visible_history[-40:]:
            visible = self._redact(ev)
            if visible is not None:
                log.write(describe_event(visible))
        seat_summaries = []
        for p in rs.players:
            pid = str(p["id"])
            name = p.get("name")
            label = f"{name} ({pid})" if name else pid
            details = f"{p.get('kind')}{':' + p['bot'] if p.get('bot') else ''}{':' + p['model'] if p.get('model') else ''}"
            seat_summaries.append(f"{label}={rs.seat.get(pid, '?')} ({details})")
        seats = "  ".join(seat_summaries)
        hand = ""
        if self.viewer:
            hand = f"\n{self.viewer}'s hand: {', '.join(rs.hands.get(self.viewer, []))}"
        elif rs.solution:
            hand = f"\nsolution (omniscient view): {' · '.join(rs.solution)}"
        self.query_one("#info", Static).update(f"{seats}{hand}\neliminated: {', '.join(sorted(rs.eliminated)) or '—'}")
        cur = rs.events[rs.idx - 1] if rs.idx else None
        turn = cur.get("turn") if cur else 0
        total = len(rs.visible_event_indices(self.viewer))
        self.query_one("#status", Static).update(f"event {self.position}/{total}  turn {turn}  {'▶' if self.playing else '⏸'} {self.delay:.1f}s  viewer: {self.viewer or 'omniscient'}  (v to change)")

    def _seek_position(self, position: int) -> None:
        indices = self.rs.visible_event_indices(self.viewer)
        self.position = max(0, min(position, len(indices)))
        actual_idx = indices[self.position - 1] + 1 if self.position else 0
        self.rs.seek(actual_idx)

    def action_next(self) -> None:
        self._seek_position(self.position + 1)
        self.render_all()

    def action_prev(self) -> None:
        self._seek_position(self.position - 1)
        self.render_all()

    def action_first(self) -> None:
        self._seek_position(0)
        self.render_all()

    def action_last(self) -> None:
        self._seek_position(len(self.rs.visible_event_indices(self.viewer)))
        self.render_all()

    def action_autoplay(self) -> None:
        self.playing = not self.playing
        self.render_all()

    def action_faster(self) -> None:
        self.delay = max(0.1, self.delay - 0.2)
        self.render_all()

    def action_slower(self) -> None:
        self.delay += 0.2
        self.render_all()

    def action_cycle_viewer(self) -> None:
        actual_idx = self.rs.idx
        self.viewer_idx = self.viewer_idx + 1 if self.viewer_idx + 1 < len(self.rs.players) else -1
        # Keep the approximate timeline while mapping it into the newly selected viewer's
        # visible stream; hidden event counts never appear in the status line.
        self.position = sum(i < actual_idx for i in self.rs.visible_event_indices(self.viewer))
        self._seek_position(self.position)
        self.render_all()


def run_replay_viewer(path: str | Path, emoji: bool = True) -> None:
    ReplayApp(load_replay(path), emoji=emoji).run()

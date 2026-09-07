"""TUI replay viewer: step through a replay (.jsonl/.json) with the board reconstructed from public events.

Keys: → / n next event, ← / b previous, space autoplay, + / - speed, g / G start / end, v cycle viewer redaction, q quit.
Only public information plus the selected viewer's private fields are shown (same redaction as the manager).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static

from clue.agents.human import describe_event
from clue.replay.state import ReplayState, load_replay
from clue.tui.board_render import render_board


class ReplayApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #top { height: 1fr; }
    #board { width: 56; height: 100%; border: round $accent; padding: 0 1; }
    #side { width: 1fr; }
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

    @property
    def viewer(self) -> str | None:
        return None if self.viewer_idx < 0 else str(self.rs.players[self.viewer_idx]["id"])

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="top"):
            yield Static(id="board")
            with Vertical(id="side"):
                yield Static(id="info")
                yield RichLog(id="log", wrap=True, markup=True, highlight=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Clue replay"
        self.query_one("#log", RichLog).border_title = "Events"
        self.query_one("#info", Static).border_title = "Game"
        self.render_all()
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        if not self.playing:
            return
        self._acc = getattr(self, "_acc", 0.0) + 0.1
        if self._acc >= self.delay:
            self._acc = 0.0
            if self.rs.idx >= len(self.rs.events):
                self.playing = False
            else:
                self.action_next()

    def _redact(self, ev: dict[str, Any]) -> dict[str, Any]:
        if ev.get("type") == "disproved" and "card" in ev and self.viewer is not None and self.viewer not in (ev.get("player"), ev.get("suggester")):
            return {k: v for k, v in ev.items() if k != "card"}
        if ev.get("type") == "disproved" and "card" in ev and self.viewer is None:
            return ev
        return ev

    def render_all(self) -> None:
        rs = self.rs
        me = rs.seat.get(self.viewer or "", rs.suspects[0])
        hl: set[str] = set()
        if rs.last_suggestion and rs.idx and rs.events[rs.idx - 1] is rs.last_suggestion:
            hl = {str(rs.last_suggestion["room"])}
        self.query_one("#board", Static).update(render_board(rs.tokens, rs.suspects, hl, rs.weapons, me, self.emoji))
        log = self.query_one("#log", RichLog)
        log.clear()
        for ev in rs.events[max(0, rs.idx - 40) : rs.idx]:
            log.write(describe_event(self._redact(ev)))
        seats = "  ".join(f"{p['id']}={rs.seat.get(p['id'], '?')} ({p.get('kind')}{':' + p['bot'] if p.get('bot') else ''}{':' + p['model'] if p.get('model') else ''})" for p in rs.players)
        hand = ""
        if self.viewer:
            hand = f"\n{self.viewer}'s hand: {', '.join(rs.hands.get(self.viewer, []))}"
        elif rs.solution:
            hand = f"\nsolution (omniscient view): {' · '.join(rs.solution)}"
        self.query_one("#info", Static).update(f"{seats}{hand}\neliminated: {', '.join(sorted(rs.eliminated)) or '—'}")
        cur = rs.events[rs.idx - 1] if rs.idx else None
        turn = cur.get("turn") if cur else 0
        self.query_one("#status", Static).update(
            f"event {rs.idx}/{len(rs.events)}  turn {turn}  {'▶' if self.playing else '⏸'} {self.delay:.1f}s  viewer: {self.viewer or 'omniscient'}  (v to change)"
        )

    def action_next(self) -> None:
        self.rs.seek(self.rs.idx + 1)
        self.render_all()

    def action_prev(self) -> None:
        self.rs.seek(self.rs.idx - 1)
        self.render_all()

    def action_first(self) -> None:
        self.rs.seek(0)
        self.render_all()

    def action_last(self) -> None:
        self.rs.seek(len(self.rs.events))
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
        self.viewer_idx = self.viewer_idx + 1 if self.viewer_idx + 1 < len(self.rs.players) else -1
        self.render_all()


def run_replay_viewer(path: str | Path, emoji: bool = True) -> None:
    ReplayApp(load_replay(path), emoji=emoji).run()

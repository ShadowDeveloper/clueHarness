"""Hybrid Clue board: 24x25 corridor grid + rooms as single nodes.

Positions are strings: a room name (e.g. "Kitchen") or "r,c" for a corridor square.
Layout is a transcription of the classic Hasbro board (room footprints, door squares,
start squares, secret passages). See RULES_SPEC.md §3 for the hybrid simplifications.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from functools import cache

from clue.rules.cards import ROOMS

ROWS, COLS = 25, 24

# (row0, row1, col0, col1) inclusive footprints; rooms may have several rects.
ROOM_RECTS: dict[str, list[tuple[int, int, int, int]]] = {
    "Kitchen": [(1, 6, 0, 5)],
    "Ballroom": [(2, 7, 8, 15), (0, 1, 10, 13)],
    "Conservatory": [(1, 5, 18, 23)],
    "Dining Room": [(9, 15, 0, 7)],
    "Lounge": [(19, 24, 0, 6)],
    "Hall": [(18, 24, 9, 14)],
    "Study": [(21, 24, 17, 23)],
    "Library": [(14, 18, 17, 23)],
    "Billiard Room": [(8, 12, 18, 23)],
}
CELLAR_RECT = (10, 16, 9, 14)  # centre "X" - not enterable

# door: room -> list of corridor squares directly outside a door
DOORS: dict[str, list[tuple[int, int]]] = {
    "Kitchen": [(7, 4)],
    "Ballroom": [(5, 7), (5, 16), (8, 9), (8, 14)],
    "Conservatory": [(6, 18)],
    "Dining Room": [(12, 8), (16, 6)],
    "Lounge": [(18, 6)],
    "Hall": [(17, 11), (17, 12), (20, 8)],
    "Study": [(20, 17)],
    "Library": [(16, 16), (13, 20)],
    "Billiard Room": [(9, 17), (13, 22)],
}
SECRET_PASSAGES: dict[str, str] = {
    "Lounge": "Conservatory",
    "Conservatory": "Lounge",
    "Kitchen": "Study",
    "Study": "Kitchen",
}
# canonical suspect order -> start squares
START_SQUARES: dict[int, tuple[int, int]] = {
    0: (24, 7),  # Miss Scarlet
    1: (17, 0),  # Col. Mustard
    2: (0, 9),  # Mrs. White
    3: (0, 14),  # Mr. Green
    4: (6, 23),  # Mrs. Peacock
    5: (19, 23),  # Prof. Plum
}


def sq(r: int, c: int) -> str:
    return f"{r},{c}"


def parse_sq(pos: str) -> tuple[int, int]:
    r, c = pos.split(",")
    return int(r), int(c)


def is_room(pos: str) -> bool:
    return pos in ROOMS


def _in_rect(r: int, c: int, rect: tuple[int, int, int, int]) -> bool:
    r0, r1, c0, c1 = rect
    return r0 <= r <= r1 and c0 <= c <= c1


@dataclass(frozen=True)
class Board:
    corridor: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    room_of_cell: dict[tuple[int, int], str] = field(default_factory=dict)
    door_room: dict[tuple[int, int], list[str]] = field(default_factory=dict)

    def neighbors(self, cell: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = cell
        out = []
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + dr, c + dc)
            if n in self.corridor:
                out.append(n)
        return out


def _build() -> Board:
    room_of_cell: dict[tuple[int, int], str] = {}
    for room, rects in ROOM_RECTS.items():
        for rect in rects:
            for r in range(rect[0], rect[1] + 1):
                for c in range(rect[2], rect[3] + 1):
                    room_of_cell[(r, c)] = room
    void: set[tuple[int, int]] = set()
    for r in range(ROWS):
        for c in range(COLS):
            if _in_rect(r, c, CELLAR_RECT):
                void.add((r, c))
    # outer edge is void except start squares and the ballroom bump
    starts = set(START_SQUARES.values())
    for c in range(COLS):
        if (0, c) not in starts:
            void.add((0, c))
        if (24, c) not in starts:
            void.add((24, c))
    for r in range(ROWS):
        if (r, 0) not in starts:
            void.add((r, 0))
        if (r, 23) not in starts:
            void.add((r, 23))
    corridor = {(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in room_of_cell and (r, c) not in void}
    door_room: dict[tuple[int, int], list[str]] = {}
    for room, cells in DOORS.items():
        for cell in cells:
            assert cell in corridor, f"door square {cell} for {room} is not corridor"
            door_room.setdefault(cell, []).append(room)
    for s in starts:
        assert s in corridor, f"start {s} not corridor"
    return Board(frozenset(corridor), room_of_cell, door_room)


BOARD: Board = _build()


@cache
def _bfs(start: tuple[int, int], blocked: frozenset[tuple[int, int]], forbid_room: str | None) -> tuple[dict[tuple[int, int], int], dict[str, int]]:
    """Shortest corridor distances from start; room distances = first door reached + 1."""
    dist: dict[tuple[int, int], int] = {start: 0}
    rooms: dict[str, int] = {}
    q = deque([start])
    while q:
        cur = q.popleft()
        d = dist[cur]
        for room in BOARD.door_room.get(cur, []):
            if room != forbid_room and room not in rooms:
                rooms[room] = d + 1
        for n in BOARD.neighbors(cur):
            if n in blocked or n in dist:
                continue
            dist[n] = d + 1
            q.append(n)
    return dist, rooms


def reachable(pos: str, steps: int, occupied: frozenset[str]) -> set[str]:
    """Destinations for a token at `pos` rolling `steps` (see RULES_SPEC §3).

    Corridor squares at exact BFS distance == steps (a shortest path is simple, so always legal),
    plus rooms reachable within `steps`. If a player is boxed in and cannot go the full roll,
    the furthest reachable squares are offered instead (rulebook silent; documented).
    """
    blocked = frozenset(parse_sq(p) for p in occupied if not is_room(p) and p != pos)
    out: set[str] = set()
    if is_room(pos):
        best_cells: dict[tuple[int, int], int] = {}
        for door in DOORS[pos]:
            if door in blocked:
                continue
            dist, rooms = _bfs(door, blocked, pos)
            for cell, d in dist.items():
                if cell not in best_cells or d + 1 < best_cells[cell]:
                    best_cells[cell] = d + 1
            for room, d in rooms.items():
                if d + 1 <= steps:
                    out.add(room)
        exact = {c for c, d in best_cells.items() if d == steps}
        out |= {sq(*c) for c in exact}
        if not out and best_cells:
            m = max(d for d in best_cells.values() if d <= steps)
            out |= {sq(*c) for c, d in best_cells.items() if d == m}
        return out
    start = parse_sq(pos)
    dist, rooms = _bfs(start, blocked, None)
    out |= {room for room, d in rooms.items() if d <= steps}
    out |= {sq(*c) for c, d in dist.items() if d == steps}
    if not out:
        cand = [d for d in dist.values() if 0 < d < steps]
        if cand:
            m = max(cand)
            out |= {sq(*c) for c, d in dist.items() if d == m}
    return out


def ascii_board(tokens: dict[str, str], labels: dict[str, str]) -> str:
    """Render the board. tokens: token_name -> position; labels: token_name -> 1-char label."""
    grid = [[" " for _ in range(COLS)] for _ in range(ROWS)]
    abbrev = {r: r[0] if r != "Billiard Room" else "I" for r in ROOMS}
    for (r, c), room in BOARD.room_of_cell.items():
        grid[r][c] = abbrev[room].lower()
    for r, c in BOARD.corridor:
        grid[r][c] = "."
    for r, c in BOARD.door_room:
        grid[r][c] = "+"
    for r in range(CELLAR_RECT[0], CELLAR_RECT[1] + 1):
        for c in range(CELLAR_RECT[2], CELLAR_RECT[3] + 1):
            grid[r][c] = "X"
    # room names in the middle of rooms
    for room, rects in ROOM_RECTS.items():
        r0, r1, c0, c1 = rects[0]
        rr = (r0 + r1) // 2
        name = room.upper()[: c1 - c0]
        cc = c0 + ((c1 - c0 + 1) - len(name)) // 2
        for i, ch in enumerate(name):
            grid[rr][cc + i] = ch
    in_room: dict[str, list[str]] = {}
    for tok, pos in tokens.items():
        if is_room(pos):
            in_room.setdefault(pos, []).append(labels[tok])
        else:
            r, c = parse_sq(pos)
            grid[r][c] = labels[tok]
    for room, labs in in_room.items():
        r0, r1, c0, c1 = ROOM_RECTS[room][0]
        rr = (r0 + r1) // 2 + 1
        for i, lab in enumerate(labs[: c1 - c0]):
            grid[rr][c0 + 1 + i] = lab
    header = "    " + "".join(str(c % 10) for c in range(COLS))
    lines = [header] + [f"{r:2d}  " + "".join(row) for r, row in enumerate(grid)]
    return "\n".join(lines)


def geometry() -> dict[str, object]:
    """Static board geometry as plain JSON-able data (for non-terminal renderers such as the web UI)."""
    rooms: dict[str, list[list[int]]] = {}
    for (r, c), room in BOARD.room_of_cell.items():
        rooms.setdefault(room, []).append([r, c])
    return {
        "rows": ROWS,
        "cols": COLS,
        "rooms": {k: sorted(v) for k, v in rooms.items()},
        "corridor": sorted([r, c] for r, c in BOARD.corridor),
        "doors": [{"cell": [r, c], "rooms": rs} for (r, c), rs in sorted(BOARD.door_room.items())],
        "passages": dict(SECRET_PASSAGES),
        "cellar": list(CELLAR_RECT),
        "starts": {str(i): [r, c] for i, (r, c) in START_SQUARES.items()},
    }

"""Hybrid Clue boards: corridor grid + rooms as single nodes.

Positions are strings: a room name (e.g. "Kitchen") or "r,c" for a corridor square.
Two layouts:
  * classic – 24x25 transcription of the Hasbro board (room footprints, door squares, start squares,
    secret passages). Used by the classic and modern editions.
  * large   – 42x40 "Hill House" mansion with 15 rooms and 12 start squares for the large edition.
See RULES_SPEC.md §3 for the hybrid simplifications. All geometry is validated at import time
(doors on corridor squares adjacent to their room, starts on corridor, every room reachable).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from functools import cache

from clue.rules.cards import PASSAGES_CLASSIC, PASSAGES_LARGE, ROOMS, ROOMS_LARGE, edition_def

Rect = tuple[int, int, int, int]  # (row0, row1, col0, col1) inclusive

# ---------------------------------------------------------------------------------------------------
# classic layout
ROWS, COLS = 25, 24
ROOM_RECTS: dict[str, list[Rect]] = {
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
CELLAR_RECT: Rect = (10, 16, 9, 14)  # centre "X" - not enterable
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
SECRET_PASSAGES: dict[str, str] = dict(PASSAGES_CLASSIC)
START_SQUARES: dict[int, tuple[int, int]] = {
    0: (24, 7),  # Miss Scarlet
    1: (17, 0),  # Col. Mustard
    2: (0, 9),  # Mrs. White
    3: (0, 14),  # Mr. Green
    4: (6, 23),  # Mrs. Peacock
    5: (19, 23),  # Prof. Plum
}

# ---------------------------------------------------------------------------------------------------
# large layout ("Hill House"): 36 cols x 36 rows, 12 rooms in three storeys of wings, 12 starts.
# Centre block = the envelope ("CONFIDENTIAL") like the classic cellar; Courtyard is a real room top-centre.
ROWS_LARGE, COLS_LARGE = 36, 36
ROOM_RECTS_LARGE: dict[str, list[Rect]] = {
    "Kitchen": [(1, 7, 0, 7)],
    "Ballroom": [(2, 8, 10, 19), (0, 1, 12, 17)],
    "Conservatory": [(1, 7, 22, 28)],
    "Attic": [(1, 6, 31, 35)],
    "Dining Room": [(10, 16, 0, 8)],
    "Courtyard": [(11, 15, 12, 18)],
    "Cellar": [(9, 14, 22, 28)],
    "Garage": [(19, 25, 0, 7)],
    "Carriage House": [(17, 23, 30, 35)],
    "Lounge": [(28, 35, 0, 7)],
    "Hall": [(28, 35, 10, 17)],
    "Gazebo": [(29, 35, 20, 26)],
}
CENTRE_LARGE: Rect = (18, 24, 12, 18)
DOORS_LARGE: dict[str, list[tuple[int, int]]] = {
    "Kitchen": [(8, 4), (4, 8)],
    "Ballroom": [(5, 9), (5, 20), (9, 12), (9, 17)],
    "Conservatory": [(8, 25), (4, 29)],
    "Attic": [(7, 33), (4, 30)],
    "Dining Room": [(13, 9), (17, 4)],
    "Courtyard": [(10, 15), (13, 11), (13, 19), (16, 15)],
    "Cellar": [(15, 25), (11, 21), (11, 29)],
    "Garage": [(18, 4), (22, 8)],
    "Carriage House": [(16, 33), (20, 29)],
    "Lounge": [(27, 4), (31, 8)],
    "Hall": [(27, 13), (31, 9), (31, 18)],
    "Gazebo": [(28, 23), (32, 19), (32, 27)],
}
START_SQUARES_LARGE: dict[int, tuple[int, int]] = {
    0: (35, 8),  # Miss Scarlet
    1: (17, 0),  # Col. Mustard
    2: (0, 9),  # Mrs. White
    3: (0, 20),  # Mr. Green
    4: (8, 35),  # Mrs. Peacock
    5: (26, 35),  # Prof. Plum
    6: (35, 18),  # Wadsworth
    7: (0, 29),  # Yvette
    8: (35, 28),  # Miss Peach
    9: (26, 0),  # Sgt. Gray
    10: (35, 19),  # Mr. Boddy
    11: (15, 35),  # Madame Rose
}

_ALL_ROOM_NAMES: frozenset[str] = frozenset(ROOMS) | frozenset(ROOMS_LARGE)


def sq(r: int, c: int) -> str:
    return f"{r},{c}"


def parse_sq(pos: str) -> tuple[int, int]:
    r, c = pos.split(",")
    return int(r), int(c)


def is_room(pos: str) -> bool:
    return pos in _ALL_ROOM_NAMES


def _in_rect(r: int, c: int, rect: tuple[int, int, int, int]) -> bool:
    r0, r1, c0, c1 = rect
    return r0 <= r <= r1 and c0 <= c <= c1


@dataclass(frozen=True, eq=False)
class Board:
    """A built board layout. `BOARD` is the classic one; use `board_for(edition)`. Hash/eq by identity."""

    name: str = "classic"
    rows: int = ROWS
    cols: int = COLS
    room_rects: dict[str, list[Rect]] = field(default_factory=dict)
    doors: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    passages: dict[str, str] = field(default_factory=dict)
    starts: dict[int, tuple[int, int]] = field(default_factory=dict)
    centre: Rect | None = None  # non-enterable centre block (classic cellar), None on the large board
    corridor: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    room_of_cell: dict[tuple[int, int], str] = field(default_factory=dict)
    door_room: dict[tuple[int, int], list[str]] = field(default_factory=dict)

    @property
    def rooms(self) -> tuple[str, ...]:
        return tuple(self.room_rects)

    def neighbors(self, cell: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = cell
        out = []
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + dr, c + dc)
            if n in self.corridor:
                out.append(n)
        return out


def _build(
    name: str,
    rows: int,
    cols: int,
    room_rects: dict[str, list[Rect]],
    doors: dict[str, list[tuple[int, int]]],
    passages: dict[str, str],
    starts: dict[int, tuple[int, int]],
    centre: Rect | None,
) -> Board:
    room_of_cell: dict[tuple[int, int], str] = {}
    for room, rects in room_rects.items():
        for rect in rects:
            for r in range(rect[0], rect[1] + 1):
                for c in range(rect[2], rect[3] + 1):
                    assert 0 <= r < rows and 0 <= c < cols, f"{room} rect {rect} outside the {rows}x{cols} grid"
                    assert (r, c) not in room_of_cell, f"{room} overlaps {room_of_cell[(r, c)]} at {(r, c)}"
                    room_of_cell[(r, c)] = room
    void: set[tuple[int, int]] = set()
    if centre:
        for r in range(rows):
            for c in range(cols):
                if _in_rect(r, c, centre):
                    void.add((r, c))
    # outer edge is void except start squares (and room cells that touch the edge)
    start_set = set(starts.values())
    for c in range(cols):
        for r in (0, rows - 1):
            if (r, c) not in start_set:
                void.add((r, c))
    for r in range(rows):
        for c in (0, cols - 1):
            if (r, c) not in start_set:
                void.add((r, c))
    corridor = {(r, c) for r in range(rows) for c in range(cols) if (r, c) not in room_of_cell and (r, c) not in void}
    door_room: dict[tuple[int, int], list[str]] = {}
    for room, cells in doors.items():
        assert room in room_rects, f"door for unknown room {room}"
        for cell in cells:
            assert cell in corridor, f"{name}: door square {cell} for {room} is not corridor"
            r, c = cell
            assert any(room_of_cell.get((r + dr, c + dc)) == room for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))), f"{name}: door {cell} does not touch {room}"
            door_room.setdefault(cell, []).append(room)
    for room in room_rects:
        assert doors.get(room), f"{name}: room {room} has no door"
    for a, b in passages.items():
        assert a in room_rects and b in room_rects and passages.get(b) == a, f"{name}: bad passage {a}->{b}"
    for s in start_set:
        assert s in corridor, f"{name}: start {s} not corridor"
    board = Board(name, rows, cols, room_rects, doors, passages, starts, centre, frozenset(corridor), room_of_cell, door_room)
    # connectivity: from the first start every door square must be reachable
    seen = {next(iter(start_set))}
    q = deque(seen)
    while q:
        cur = q.popleft()
        for n in board.neighbors(cur):
            if n not in seen:
                seen.add(n)
                q.append(n)
    for cell in door_room:
        assert cell in seen, f"{name}: door {cell} unreachable"
    for s in start_set:
        assert s in seen, f"{name}: start {s} unreachable"
    return board


BOARD: Board = _build("classic", ROWS, COLS, ROOM_RECTS, DOORS, SECRET_PASSAGES, START_SQUARES, CELLAR_RECT)
BOARD_LARGE: Board = _build("large", ROWS_LARGE, COLS_LARGE, ROOM_RECTS_LARGE, DOORS_LARGE, dict(PASSAGES_LARGE), START_SQUARES_LARGE, CENTRE_LARGE)


def board_for(edition: str = "classic") -> Board:
    """The board layout used by an edition (classic/modern share the Hasbro board)."""
    board = BOARD_LARGE if edition == "large" else BOARD
    assert set(board.rooms) == set(edition_def(edition).rooms), f"board {board.name} does not match edition {edition} rooms"
    return board


def passages_for(edition: str = "classic") -> dict[str, str]:
    return board_for(edition).passages


@cache
def _bfs(board: Board, start: tuple[int, int], blocked: frozenset[tuple[int, int]], forbid_room: str | None) -> tuple[dict[tuple[int, int], int], dict[str, int]]:
    """Shortest corridor distances from start; room distances = first door reached + 1."""
    dist: dict[tuple[int, int], int] = {start: 0}
    rooms: dict[str, int] = {}
    q = deque([start])
    while q:
        cur = q.popleft()
        d = dist[cur]
        for room in board.door_room.get(cur, []):
            if room != forbid_room and room not in rooms:
                rooms[room] = d + 1
        for n in board.neighbors(cur):
            if n in blocked or n in dist:
                continue
            dist[n] = d + 1
            q.append(n)
    return dist, rooms


def reachable(pos: str, steps: int, occupied: frozenset[str], edition: str = "classic") -> set[str]:
    """Destinations for a token at `pos` rolling `steps` (see RULES_SPEC §3).

    Corridor squares at exact BFS distance == steps (a shortest path is simple, so always legal),
    plus rooms reachable within `steps`. If a player is boxed in and cannot go the full roll,
    the furthest reachable squares are offered instead (rulebook silent; documented).
    """
    board = board_for(edition)
    blocked = frozenset(parse_sq(p) for p in occupied if not is_room(p) and p != pos)
    out: set[str] = set()
    if is_room(pos):
        best_cells: dict[tuple[int, int], int] = {}
        for door in board.doors[pos]:
            if door in blocked:
                continue
            dist, rooms = _bfs(board, door, blocked, pos)
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
    dist, rooms = _bfs(board, start, blocked, None)
    out |= {room for room, d in rooms.items() if d <= steps}
    out |= {sq(*c) for c, d in dist.items() if d == steps}
    if not out:
        cand = [d for d in dist.values() if 0 < d < steps]
        if cand:
            m = max(cand)
            out |= {sq(*c) for c, d in dist.items() if d == m}
    return out


def ascii_board(tokens: dict[str, str], labels: dict[str, str], edition: str = "classic") -> str:
    """Render the board. tokens: token_name -> position; labels: token_name -> 1-char label."""
    board = board_for(edition)
    grid = [[" " for _ in range(board.cols)] for _ in range(board.rows)]
    abbrev: dict[str, str] = {}
    used: set[str] = set()
    for room in board.rooms:
        ch = next((c for c in room.replace(" ", "") if c.upper() not in used), room[0])
        used.add(ch.upper())
        abbrev[room] = ch.upper()
    for (r, c), room in board.room_of_cell.items():
        grid[r][c] = abbrev[room].lower()
    for r, c in board.corridor:
        grid[r][c] = "."
    for r, c in board.door_room:
        grid[r][c] = "+"
    if board.centre:
        for r in range(board.centre[0], board.centre[1] + 1):
            for c in range(board.centre[2], board.centre[3] + 1):
                grid[r][c] = "X"
    # room names in the middle of rooms
    for room, rects in board.room_rects.items():
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
        r0, r1, c0, c1 = board.room_rects[room][0]
        rr = (r0 + r1) // 2 + 1
        for i, lab in enumerate(labs[: c1 - c0]):
            grid[rr][c0 + 1 + i] = lab
    header = "    " + "".join(str(c % 10) for c in range(board.cols))
    lines = [header] + [f"{r:2d}  " + "".join(row) for r, row in enumerate(grid)]
    return "\n".join(lines)


def geometry(edition: str = "classic") -> dict[str, object]:
    """Static board geometry as plain JSON-able data (for non-terminal renderers such as the web UI)."""
    board = board_for(edition)
    rooms: dict[str, list[list[int]]] = {}
    for (r, c), room in board.room_of_cell.items():
        rooms.setdefault(room, []).append([r, c])
    return {
        "edition": edition,
        "rows": board.rows,
        "cols": board.cols,
        "rooms": {k: sorted(v) for k, v in rooms.items()},
        "corridor": sorted([r, c] for r, c in board.corridor),
        "doors": [{"cell": [r, c], "rooms": rs} for (r, c), rs in sorted(board.door_room.items())],
        "passages": dict(board.passages),
        "cellar": list(board.centre) if board.centre else None,
        "starts": {str(i): [r, c] for i, (r, c) in board.starts.items()},
    }

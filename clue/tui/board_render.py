"""Rich rendering of the Clue board for the TUI.

Each grid cell is 2 characters wide so the 24×25 board is roughly square on screen.
Rooms are shaded blocks with their name; corridor squares are dots; door squares are marked;
tokens are coloured letters; reachable destinations are highlighted.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from clue.rules import board as B

TOKEN_LABELS = "SMWGKPBYHATR"  # + Butler(Wadsworth) Yvette peacH grAy boddy(T) Rose
# monochrome symbol per token (text-presentation Unicode, 1 cell wide, padded to the 2-cell grid;
# terminals render these in the foreground colour rather than as colour emoji)
TOKEN_EMOJI = {
    "S": "♛",  # Miss Scarlet — queen
    "M": "★",  # Col. Mustard — star / medal
    "W": "✚",  # Mrs. White / Dr. Orchid — cross
    "G": "♣",  # Mr. Green — club
    "K": "❋",  # Mrs. Peacock — plume
    "P": "✎",  # Prof. Plum — pencil
    "B": "♜",  # Wadsworth — the butler holds the keys to the castle
    "Y": "❀",  # Yvette — flower
    "H": "♡",  # Miss Peach
    "A": "☗",  # Sgt. Gray — badge
    "T": "☠",  # Mr. Boddy
    "R": "❦",  # Madame Rose
}
TOKEN_STYLE = {
    "S": Style(color="black", bgcolor="bright_red", bold=True),
    "M": Style(color="black", bgcolor="yellow", bold=True),
    "W": Style(color="black", bgcolor="bright_white", bold=True),
    "G": Style(color="black", bgcolor="bright_green", bold=True),
    "K": Style(color="white", bgcolor="blue", bold=True),
    "P": Style(color="white", bgcolor="magenta", bold=True),
    "B": Style(color="black", bgcolor="grey70", bold=True),
    "Y": Style(color="black", bgcolor="bright_cyan", bold=True),
    "H": Style(color="black", bgcolor="orange1", bold=True),
    "A": Style(color="white", bgcolor="grey42", bold=True),
    "T": Style(color="white", bgcolor="dark_red", bold=True),
    "R": Style(color="white", bgcolor="deep_pink4", bold=True),
}


def token_glyph(label: str, emoji: bool = True) -> str:
    """2-column glyph for a token: monochrome symbol + space, or the letter + space."""
    return (TOKEN_EMOJI[label] if emoji else label) + " "


ROOM_BG = {
    "Kitchen": "grey27",
    "Ballroom": "grey30",
    "Conservatory": "grey27",
    "Dining Room": "grey30",
    "Lounge": "grey27",
    "Hall": "grey30",
    "Study": "grey27",
    "Library": "grey30",
    "Billiard Room": "grey27",
    "Attic": "grey30",
    "Cellar": "grey23",
    "Garage": "grey27",
    "Gazebo": "grey30",
    "Courtyard": "grey35",
    "Carriage House": "grey27",
}
CORRIDOR = Style(color="grey50")
DOOR = Style(color="bright_cyan", bold=True)
CELLAR = Style(color="grey35", bgcolor="grey11")
HILITE = Style(color="black", bgcolor="bright_yellow", bold=True)
ROOM_NAME = Style(color="grey85", bold=True)
ROOM_NAME_HL = Style(color="black", bgcolor="bright_yellow", bold=True)
SHORT = {
    "Dining Room": "DINING",
    "Billiard Room": "BILLIARD",
    "Conservatory": "CONSERV.",
    "Kitchen": "KITCHEN",
    "Ballroom": "BALLROOM",
    "Lounge": "LOUNGE",
    "Hall": "HALL",
    "Study": "STUDY",
    "Library": "LIBRARY",
    "Attic": "ATTIC",
    "Cellar": "CELLAR",
    "Garage": "GARAGE",
    "Gazebo": "GAZEBO",
    "Courtyard": "COURTYARD",
    "Carriage House": "CARRIAGE",
}


def token_labels(suspects: list[str]) -> dict[str, str]:
    """suspect name -> 1-char label, in seat order (works for the classic 6 and the large 12)."""
    return dict(zip(suspects, TOKEN_LABELS[: len(suspects)], strict=True))


def render_board(
    tokens: dict[str, str],
    suspects: list[str],
    highlight: set[str] | None = None,
    weapons: dict[str, str] | None = None,
    you: str | None = None,
    emoji: bool = True,
    edition: str = "classic",
) -> Text:
    highlight = highlight or set()
    labels = token_labels(suspects)
    board = B.board_for(edition)
    # cell -> (text2, style)
    cells: dict[tuple[int, int], tuple[str, Style]] = {}
    for r in range(board.rows):
        for c in range(board.cols):
            cells[(r, c)] = ("  ", Style())
    for (r, c), room in board.room_of_cell.items():
        cells[(r, c)] = ("  ", Style(bgcolor=ROOM_BG[room]))
    for r, c in board.corridor:
        cells[(r, c)] = ("· ", CORRIDOR)
    for r, c in board.door_room:
        cells[(r, c)] = ("▢ ", DOOR)
    if board.centre:
        r0, r1, c0, c1 = board.centre
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cells[(r, c)] = ("░░", CELLAR)
    # room names (middle row of main rect)
    for room in board.rooms:
        rr0, rr1, cc0, cc1 = board.room_rects[room][0]
        mid = (rr0 + rr1) // 2
        name = SHORT[room]
        width = (cc1 - cc0 + 1) * 2
        name = name[:width]
        start = cc0 * 2 + (width - len(name)) // 2
        style = ROOM_NAME_HL if room in highlight else ROOM_NAME
        for i in range(0, len(name), 2):
            col = (start + i) // 2
            chunk = name[i : i + 2].ljust(2)
            cells[(mid, col)] = (chunk, Style(bgcolor=ROOM_BG[room]) + style)
        if room in board.passages:
            cells[(rr1, cc1)] = ("⇄ ", Style(bgcolor=ROOM_BG[room], color="bright_cyan"))
    # highlighted corridor destinations
    for pos in highlight:
        if not B.is_room(pos):
            cells[B.parse_sq(pos)] = ("◆ ", HILITE)
    # weapons: small marker in room bottom-left
    if weapons:
        by_room: dict[str, list[str]] = {}
        for w, room in weapons.items():
            by_room.setdefault(room, []).append(w[0].lower())
        for room, ws in by_room.items():
            rr0, rr1, cc0, cc1 = board.room_rects[room][0]
            for i, w in enumerate(ws[:3]):
                cells[(rr1, cc0 + i)] = (w + " ", Style(bgcolor=ROOM_BG[room], color="grey58"))
    # tokens
    in_room: dict[str, list[str]] = {}
    for suspect, pos in tokens.items():
        lab = labels[suspect]
        if B.is_room(pos):
            in_room.setdefault(pos, []).append(lab)
        else:
            cells[B.parse_sq(pos)] = (token_glyph(lab, emoji), TOKEN_STYLE[lab])
    for room, labs in in_room.items():
        rr0, rr1, cc0, cc1 = board.room_rects[room][0]
        row = (rr0 + rr1) // 2 + 1
        width = cc1 - cc0 - 1
        for i, lab in enumerate(labs):
            cells[(row + i // width, cc0 + 1 + i % width)] = (token_glyph(lab, emoji), TOKEN_STYLE[lab])
    # assemble
    t = Text()
    t.append("    " + "".join(f"{c:<2d}" for c in range(board.cols)) + "\n", style="grey50")
    for r in range(board.rows):
        t.append(f"{r:>2}  ", style="grey50")
        for c in range(board.cols):
            s, st = cells[(r, c)]
            t.append(s, style=st)
        t.append("\n")
    # legend (two columns when there are many tokens)
    t.append("\n")
    per_col = 6
    for j in range(min(per_col, len(suspects))):
        for suspect in suspects[j::per_col]:
            lab = labels[suspect]
            t.append(f" {token_glyph(lab, emoji)} ", style=TOKEN_STYLE[lab])
            t.append((" " + suspect + ("  ← you" if you == suspect else "")).ljust(22))
        t.append("\n")
    t.append(" ▢ ", style=DOOR)
    t.append("door  ")
    t.append(" ⇄ ", style="bright_cyan")
    t.append("passage  ")
    t.append(" ◆ ", style=HILITE)
    t.append("reachable  ")
    t.append(" ░ ", style=CELLAR)
    t.append("cellar\n")
    return t

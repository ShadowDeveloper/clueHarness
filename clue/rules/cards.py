"""Card definitions for Clue editions. Pure data, no I/O.

Editions
  classic  – Classic US Clue (6 suspects / 6 weapons / 9 rooms, 21 cards, 3–6 players)
  modern   – classic with Dr. Orchid replacing Mrs. White
  large    – "Hill House, full staff": 12 suspects / 12 weapons / 12 rooms (36 cards, 3–12 players).
             Six classic suspects + film characters (Wadsworth, Yvette, Mr. Boddy, Miss Peach, Sgt. Gray,
             Madame Rose); six classic weapons + six more; six classic rooms + Attic, Cellar, Garage, Gazebo,
             Courtyard, Carriage House.

Module-level SUSPECTS_CLASSIC / WEAPONS / ROOMS remain the *classic* lists for backwards compatibility;
edition-aware code should call suspects(edition) / weapons(edition) / rooms(edition).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Edition = Literal["classic", "modern", "large"]
EDITIONS: tuple[Edition, ...] = ("classic", "modern", "large")

SUSPECTS_CLASSIC: tuple[str, ...] = (
    "Miss Scarlet",
    "Col. Mustard",
    "Mrs. White",
    "Mr. Green",
    "Mrs. Peacock",
    "Prof. Plum",
)
SUSPECTS_MODERN: tuple[str, ...] = tuple("Dr. Orchid" if s == "Mrs. White" else s for s in SUSPECTS_CLASSIC)
WEAPONS: tuple[str, ...] = ("Candlestick", "Dagger", "Lead Pipe", "Revolver", "Rope", "Wrench")
ROOMS: tuple[str, ...] = (
    "Hall",
    "Lounge",
    "Dining Room",
    "Kitchen",
    "Ballroom",
    "Conservatory",
    "Billiard Room",
    "Library",
    "Study",
)

# ---- large edition -------------------------------------------------------------------------------
SUSPECTS_LARGE: tuple[str, ...] = SUSPECTS_CLASSIC + (
    "Wadsworth",  # the butler
    "Yvette",  # the maid
    "Miss Peach",
    "Sgt. Gray",
    "Mr. Boddy",
    "Madame Rose",
)
WEAPONS_LARGE: tuple[str, ...] = WEAPONS + (
    "Poison",
    "Horseshoe",
    "Axe",
    "Trophy",
    "Poker",
    "Garden Shears",
)
# 12 rooms: six classics that survive the film's renovation + the six new locations
ROOMS_LARGE: tuple[str, ...] = (
    "Hall",
    "Lounge",
    "Dining Room",
    "Kitchen",
    "Ballroom",
    "Conservatory",
    "Attic",
    "Cellar",
    "Garage",
    "Gazebo",
    "Courtyard",
    "Carriage House",
)
# secret passages: pairs of opposite corners (classic) + two more for the large house
PASSAGES_CLASSIC: dict[str, str] = {"Lounge": "Conservatory", "Conservatory": "Lounge", "Kitchen": "Study", "Study": "Kitchen"}
PASSAGES_LARGE: dict[str, str] = {
    "Kitchen": "Carriage House",
    "Carriage House": "Kitchen",
    "Attic": "Lounge",
    "Lounge": "Attic",
    "Cellar": "Gazebo",
    "Gazebo": "Cellar",
}


@dataclass(frozen=True)
class EditionDef:
    name: Edition
    suspects: tuple[str, ...]
    weapons: tuple[str, ...]
    rooms: tuple[str, ...]
    max_players: int
    label: str

    @property
    def cards(self) -> tuple[str, ...]:
        return self.suspects + self.weapons + self.rooms

    @property
    def n_dealt(self) -> int:
        """Cards dealt to players (all cards minus the three in the envelope)."""
        return len(self.cards) - 3


_EDITIONS: dict[str, EditionDef] = {
    "classic": EditionDef("classic", SUSPECTS_CLASSIC, WEAPONS, ROOMS, 6, "Classic (6·6·9, 3–6 players)"),
    "modern": EditionDef("modern", SUSPECTS_MODERN, WEAPONS, ROOMS, 6, "Modern 2016 (Dr. Orchid)"),
    "large": EditionDef("large", SUSPECTS_LARGE, WEAPONS_LARGE, ROOMS_LARGE, 12, "Large — Hill House (12·12·12, 3–12 players)"),
}


def edition_def(edition: str = "classic") -> EditionDef:
    try:
        return _EDITIONS[edition]
    except KeyError:
        raise ValueError(f"Unknown edition: {edition!r} (choose from {', '.join(_EDITIONS)})") from None


def suspects(edition: str = "classic") -> tuple[str, ...]:
    return edition_def(edition).suspects


def weapons(edition: str = "classic") -> tuple[str, ...]:
    return edition_def(edition).weapons


def rooms(edition: str = "classic") -> tuple[str, ...]:
    return edition_def(edition).rooms


def all_cards(edition: str = "classic") -> tuple[str, ...]:
    return edition_def(edition).cards


def category(card: str, edition: str = "classic") -> str:
    ed = edition_def(edition)
    if card in ed.suspects:
        return "suspect"
    if card in ed.weapons:
        return "weapon"
    if card in ed.rooms:
        return "room"
    raise ValueError(f"Unknown card: {card!r}")


def max_players(edition: str = "classic") -> int:
    return edition_def(edition).max_players

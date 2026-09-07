"""Card definitions for Classic US Clue. Pure data, no I/O."""

from __future__ import annotations

from typing import Literal

Edition = Literal["classic", "modern"]

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


def suspects(edition: Edition = "classic") -> tuple[str, ...]:
    return SUSPECTS_MODERN if edition == "modern" else SUSPECTS_CLASSIC


def all_cards(edition: Edition = "classic") -> tuple[str, ...]:
    return suspects(edition) + WEAPONS + ROOMS


def category(card: str, edition: Edition = "classic") -> str:
    if card in suspects(edition):
        return "suspect"
    if card in WEAPONS:
        return "weapon"
    if card in ROOMS:
        return "room"
    raise ValueError(f"Unknown card: {card!r}")

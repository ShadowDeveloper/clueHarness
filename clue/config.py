"""YAML game config loading -> (GameConfig, [PlayerSpec], seed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clue.agents.factory import STRATEGY_ALIASES
from clue.manager import PlayerSpec
from clue.rules import GameConfig

EDITION_ALIASES = {
    "classic": "classic",
    "classic-clue-1996": "classic",
    "classic-clue-2002": "classic",
    "modern": "modern",
    "modern-2016": "modern",
    "large": "large",
    "hill-house": "large",
    "12": "large",
}


def load_yaml_config(path: str | Path) -> tuple[GameConfig, list[PlayerSpec], int, dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    players = []
    for i, p in enumerate(data.get("players", [])):
        p = dict(p)
        p.setdefault("id", f"P{i + 1}")
        if "strategy" in p and p["strategy"] in STRATEGY_ALIASES:
            p["strategy"] = STRATEGY_ALIASES[p["strategy"]]
        players.append(PlayerSpec(**p))
    edition_raw = str(data.get("edition", "classic"))
    dice = data.get("dice", 1 if edition_raw == "classic-clue-1996" else 2)
    cfg = GameConfig(
        edition=EDITION_ALIASES.get(edition_raw, "classic"),  # type: ignore[arg-type]
        dice=dice,
        deal_remainder=data.get("deal_remainder", "uneven"),
        num_players=len(players),
        max_turns=data.get("max_turns", 400),
    )
    return cfg, players, int(data.get("seed", 0)), data  # data["ponder"] read by the CLI

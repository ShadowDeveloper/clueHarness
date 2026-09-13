from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from clue.agents.llm_client import GLOBAL_COST, CostTracker
from clue.rules import GameConfig
from clue.rules.board import geometry
from clue.rules.cards import EDITIONS, edition_def, rooms, suspects, weapons
from clue.web.deps import registry, settings
from clue.web.sessions import Registry
from clue.web.settings import WebSettings

router = APIRouter()
_START = time.time()


@router.get("/health")
def health(reg: Registry = Depends(registry)) -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        v = version("clue-harness")
    except PackageNotFoundError:
        v = "dev"
    return {"ok": True, "version": v, "uptime_s": round(time.time() - _START, 1), "games": len(reg.games), "tournaments": len(reg.tournaments), "cost": GLOBAL_COST.summary()}


@router.get("/board")
def board(edition: str = "classic") -> dict[str, Any]:
    """Static board geometry for an edition (classic/modern share the Hasbro board; large = Hill House)."""
    try:
        return geometry(edition)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/catalog")
def catalog(st: WebSettings = Depends(settings)) -> dict[str, Any]:
    strategies = sorted(p.stem for p in Path("strategies").glob("*.md")) if Path("strategies").exists() else []
    provider = os.getenv("CLUE_LLM_PROVIDER") or "mock"
    return {
        "kinds": ["human", "baseline", "llm"],
        "bots": ["heuristic", "expert", "random"],
        "strategies": strategies,
        "tool_modes": ["precomputed", "native", "none"],
        "prompt_profiles": ["full", "compact"],
        "providers": ["mock", "openrouter", "openai", "local", "anthropic"],
        "default_provider": provider,
        "default_model": os.getenv("CLUE_LLM_MODEL") or "mock",
        "known_models": sorted(CostTracker.PRICES),
        "config_defaults": GameConfig(num_players=3).model_dump(),
        "config_schema": GameConfig.model_json_schema(),
        "cards": {"suspects": list(suspects("classic")), "weapons": list(weapons("classic")), "rooms": list(rooms("classic"))},
        "editions": [
            {
                "id": ed,
                "label": edition_def(ed).label,
                "max_players": edition_def(ed).max_players,
                "cards": {"suspects": list(suspects(ed)), "weapons": list(weapons(ed)), "rooms": list(rooms(ed))},
            }
            for ed in EDITIONS
        ],
        "hotseat": st.hotseat,
        "remote": st.remote,
        "saves_dir": str(st.saves_dir),
        "replay_dir": str(st.replay_dir),
    }

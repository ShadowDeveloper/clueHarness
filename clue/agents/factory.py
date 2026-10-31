"""Build PlayerAgents from PlayerSpecs (config file or CLI shorthand)."""

from __future__ import annotations

from typing import Any

from clue.agents.base import PlayerAgent
from clue.agents.baselines import BaselineHeuristicBot, BaselineRandomBot
from clue.agents.expert import BaselineExpertBot
from clue.agents.human import HumanCLIAgent
from clue.agents.llm_agent import LLMPlayerAgent
from clue.agents.llm_client import LLMClient, LLMConnection
from clue.manager.game_manager import PlayerSpec

STRATEGY_ALIASES = {
    "conservative": "strategies/conservative_notebook.md",
    "aggressive": "strategies/aggressive_accuser.md",
    "bayesian": "strategies/bayesian_probabilist.md",
    "info_value_hunter": "strategies/info_value_hunter.md",
    "info": "strategies/info_value_hunter.md",
    "deceptive": "strategies/deceptive_misdirector.md",
    "room_rusher": "strategies/room_rusher.md",
    "rusher": "strategies/room_rusher.md",
}


def parse_players_arg(arg: str) -> list[PlayerSpec]:
    """Parse `human,llm:bayesian,llm:aggressive:gpt-4o,baseline,baseline:random,baseline:expert,llm:bayesian:notools`.

    LLM flags after the strategy/model: `notools` (ablation), `native` (function calling), `compact` (short prompt).
    """
    specs = []
    for i, tok in enumerate([t.strip() for t in arg.split(",") if t.strip()]):
        parts = tok.split(":")
        kind = parts[0]
        pid = f"P{i + 1}"
        if kind == "human":
            specs.append(PlayerSpec(id=pid, kind="human", name="You"))
        elif kind == "baseline":
            specs.append(PlayerSpec(id=pid, kind="baseline", bot=parts[1] if len(parts) > 1 else "heuristic"))
        elif kind == "llm":
            strat = parts[1] if len(parts) > 1 and parts[1] not in ("none", "") else None
            model = parts[2] if len(parts) > 2 and parts[2] not in ("notools",) else None
            tools = "notools" not in parts
            tool_mode = "native" if "native" in parts else None
            model = None if model in ("native", "compact") else model
            profile = "compact" if "compact" in parts else "full"
            spec = PlayerSpec(id=pid, kind="llm", model=model, strategy=STRATEGY_ALIASES.get(strat or "", strat), tools=tools, tool_mode=tool_mode, prompt_profile=profile)
            specs.append(spec)
        else:
            raise ValueError(f"unknown player kind {kind!r}")
    return specs


def make_agent(
    spec: PlayerSpec,
    seed: int = 0,
    client: LLMClient | None = None,
    provider: str | None = None,
    input_fn: Any = None,
    ui: str = "cli",
    connection: LLMConnection | None = None,
) -> PlayerAgent:
    if spec.kind == "human":
        if ui == "tui":
            from clue.tui.app import TUIHumanAgent

            return TUIHumanAgent(spec.id)
        return HumanCLIAgent(spec.id, input_fn) if input_fn else HumanCLIAgent(spec.id)
    if spec.kind == "baseline":
        bot = (spec.bot or "heuristic").strip().lower()
        if bot == "none":
            bot = "heuristic"
        if bot == "random":
            return BaselineRandomBot(spec.id, seed=seed)
        if bot == "expert":
            return BaselineExpertBot(spec.id, seed=seed)
        if bot == "heuristic":
            return BaselineHeuristicBot(spec.id, seed=seed)
        raise ValueError(f"unknown baseline bot {spec.bot!r}; choose none, heuristic, random, or expert")
    if spec.kind == "llm":
        return LLMPlayerAgent(
            spec.id,
            client=client,
            model=spec.model,
            provider=provider,
            strategy_path=spec.strategy,
            temperature=spec.temperature if spec.temperature is not None else 0.2,
            use_tools=spec.tools,
            seed=seed,
            tool_mode=spec.tool_mode,
            prompt_profile=spec.prompt_profile,
            connection=connection,
        )
    raise ValueError(f"unknown kind {spec.kind}")

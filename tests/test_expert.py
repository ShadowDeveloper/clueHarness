"""BaselineExpertBot: legality, determinism, and strength sanity."""

from __future__ import annotations

import random

from clue.agents.expert import BaselineExpertBot
from clue.agents.factory import make_agent, parse_players_arg
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game


def _game(seed: int, players: str = "baseline:expert,baseline,baseline") -> GameManager:
    specs = parse_players_arg(players)
    gm = GameManager.create(specs, seed=seed)
    agents = {s.id: make_agent(s, seed=seed) for s in specs}
    run_game(gm, agents)
    return gm


def test_expert_registered_and_legal() -> None:
    gm = _game(3)
    s = gm.summary()
    assert isinstance(make_agent(parse_players_arg("baseline:expert")[0]), BaselineExpertBot)
    assert all(v == 0 for v in s["illegal_attempts"].values())
    assert s["winner"] is not None


def test_expert_deterministic_replay() -> None:
    a, b = _game(11), _game(11)
    assert a.replay_hash() == b.replay_hash()


def test_expert_never_false_accuses_without_gamble() -> None:
    for seed in range(4):
        specs = parse_players_arg("baseline:expert,baseline,baseline,baseline")
        gm = GameManager.create(specs, seed=seed)
        agents = {s.id: (BaselineExpertBot(s.id, seed=seed, gamble=False) if s.bot == "expert" else make_agent(s, seed=seed)) for s in specs}
        run_game(gm, agents)
        assert "P1" not in gm.summary()["false_accusations"]


def test_expert_show_card_prefers_already_shown() -> None:
    bot = BaselineExpertBot("P1", seed=0)
    obs = {"turn": {"pending_suggestion": {"suggester": "P2"}}, "you": {"hand": ["Rope", "Knife", "Hall"]}}
    first = bot.choose_card_to_show(obs, ["Rope", "Knife"])
    assert first in ("Rope", "Knife")
    assert bot.choose_card_to_show(obs, ["Rope", "Knife"]) == first  # re-show the same card


def test_expert_beats_random_bots() -> None:
    wins = 0
    for seed in range(6):
        specs = parse_players_arg("baseline:expert,baseline:random,baseline:random")
        random.Random(seed).shuffle(specs)
        specs = [s.model_copy(update={"id": f"P{i + 1}"}) for i, s in enumerate(specs)]
        gm = GameManager.create(specs, seed=seed)
        agents = {s.id: make_agent(s, seed=seed) for s in specs}
        run_game(gm, agents)
        ex = next(s.id for s in specs if s.bot == "expert")
        wins += gm.summary()["winner"] == ex
    assert wins >= 4

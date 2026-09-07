"""Generate demo_game.md: a 4-player game Human + 3 AI. The 'human' is driven by a scripted
input function that mirrors what a player would type (picks the heuristic bot's recommendation)."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import io

from rich.console import Console

from clue.agents import human as H
from clue.agents.baselines import BaselineHeuristicBot
from clue.agents.factory import make_agent
from clue.agents.human import HumanCLIAgent
from clue.agents.llm_client import MockLLMClient
from clue.config import load_yaml_config
from clue.manager import GameManager
from clue.manager.runner import run_game

cfg, specs, seed, _ = load_yaml_config("game.yaml")
gm = GameManager.create(specs, seed=seed, config=cfg)
buf = io.StringIO()
H.console = Console(file=buf, width=110, force_terminal=False, color_system=None)
advisor = BaselineHeuristicBot("P1", seed=1)
menu: list[str] = []
typed: list[str] = []


class ScriptedHuman(HumanCLIAgent):
    def _pick(self, prompt: str, options: list[str]) -> int:
        obs = self._obs
        rec = advisor.choose_action(obs, self._legal) if prompt.startswith("Your") else None
        if rec is not None:
            key = rec.key()
            want = "suggest" if rec.type == "suggest" else ("ACCUSE" if rec.type == "accuse" else key)
            idx = next((i for i, o in enumerate(options) if o.startswith(want)), 0)
            self._rec = rec
        elif prompt.startswith("Suspect"):
            idx = options.index(self._rec.suspect)
        elif prompt.startswith("Weapon"):
            idx = options.index(self._rec.weapon)
        elif prompt.startswith("Room"):
            idx = options.index(self._rec.room)
        else:  # show card
            idx = 0
        for i, o in enumerate(options):
            H.console.print(f"  [{i}] {o}")
        H.console.print(f"{prompt}{idx}")
        return idx

    def choose_action(self, observation, legal_actions):
        self._obs, self._legal = observation, legal_actions
        return super().choose_action(observation, legal_actions)


agents = {s.id: make_agent(s, seed=seed + i, client=MockLLMClient()) for i, s in enumerate(specs)}
agents["P1"] = ScriptedHuman("P1")
run_game(gm, agents)
text = buf.getvalue()
s = gm.summary()
md = [
    "# Demo game transcript — Human (P1) + 3 AI",
    "",
    f"Config: `game.yaml` (seed {seed}, {cfg.dice} dice, edition {cfg.edition}). Players: " + ", ".join(f"{x.id}={x.label()}" for x in specs),
    "",
    "The human seat is driven by a scripted stdin here so the transcript is reproducible; the numbered menus are exactly what an interactive player sees.",
    "LLM seats use the offline MockLLM (they follow the symbolic tool recommendation). Shown cards appear only because P1 was the suggester or the shower.",
    "",
    f"**Result:** winner = {s['winner']}, solution = {s['solution']}, turns = {s['turns']}, illegal attempts = {s['illegal_attempts'] or 0}",
    "",
    "```text",
    text.rstrip(),
    "```",
    "",
    "## Replay privacy check",
    "",
    "The unredacted replay (`replays/game_42.jsonl`) contains every shown card; the redacted view for P3 (`replays/game_42_redacted_P3.json`) shows `disproved` events "
    "without a `card` field unless P3 was involved:",
    "",
]
gm.write_replay("replays/game_42.jsonl")
for pid in gm.player_ids():
    gm.write_replay(f"replays/game_42_redacted_{pid}.json", viewer=pid)
red = [r for r in gm.export_replay("P3") if r.get("type") == "disproved"][:4]
full = [r for r in gm.export_replay(None) if r.get("type") == "disproved"][:4]
md += ["```json", "// unredacted"] + [str(r) for r in full] + ["// redacted for P3"] + [str(r) for r in red] + ["```"]
open("demo_game.md", "w").write("\n".join(md))
print(s)

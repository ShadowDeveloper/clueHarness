"""Eval: Random vs Heuristic vs LLM+tools vs LLM no-tools (+ strategy comparison). Writes report.md and charts.png.

Offline by default (MockLLM). `live=True` uses the provider configured in .env.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clue.agents.llm_client import MockLLMClient
from clue.eval.tournament import markdown_table, run_tournament
from clue.manager import PlayerSpec


def _client(live: bool) -> Any:
    if live:
        return None  # factory uses env provider
    # The offline mock echoes the symbolic recommendation when present; without tools the
    # "no-tools" agent gets an unguided reply (random legal action) which mimics an LLM playing by vibes.
    return MockLLMClient(garbage_rate=0.02)


def run_eval(games: int = 50, seed: int = 0, out_dir: str = "eval", live: bool = False) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = _client(live)
    model = None if live else "mock"

    main_specs = [
        PlayerSpec(id="P1", kind="baseline", bot="random"),
        PlayerSpec(id="P2", kind="baseline", bot="heuristic"),
        PlayerSpec(id="P3", kind="llm", model=model, strategy="strategies/bayesian_probabilist.md", tools=True),
        PlayerSpec(id="P4", kind="llm", model=model, strategy="strategies/bayesian_probabilist.md", tools=False),
    ]
    main = run_tournament(main_specs, games, seed=seed, client=client)

    strat_specs = [
        PlayerSpec(id="P1", kind="llm", model=model, strategy="strategies/conservative_notebook.md"),
        PlayerSpec(id="P2", kind="llm", model=model, strategy="strategies/aggressive_accuser.md"),
        PlayerSpec(id="P3", kind="llm", model=model, strategy="strategies/bayesian_probabilist.md"),
        PlayerSpec(id="P4", kind="llm", model=model, strategy="strategies/room_rusher.md"),
    ]
    strat = run_tournament(strat_specs, games, seed=seed + 10_000, client=client)

    report = {"main": main, "strategies": strat, "live": live}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    md = [
        "# Clue harness evaluation report",
        f"Games per bracket: **{games}**, base seed {seed}, mode: **{'LIVE LLM' if live else 'OFFLINE (MockLLM)'}**.",
        "",
        "## Bracket A — Random vs Heuristic vs LLM+tools vs LLM no-tools",
        markdown_table(main),
        "",
        "## Bracket B — Strategy comparison (same model, different strategy prompts)",
        markdown_table(strat),
        "",
        "## Notes",
        "- In OFFLINE mode the MockLLM follows the symbolic `recommended_action` when tools are on, and plays"
        " an unguided legal action otherwise; the ablation therefore measures the value of the tool layer, not of any"
        " particular model. Strategy prompts only change behaviour when a real LLM reads them, so bracket B is expected"
        " to be flat offline — run with `--live` to measure strategy effects.",
        "- `false_accusation_rate` = fraction of games in which the agent made a wrong accusation.",
        "- ELO uses pairwise winner-vs-loser updates (K=24) starting at 1000.",
    ]
    (out / "report.md").write_text("\n".join(md))
    try:
        _charts(report, out / "charts.png")
    except Exception as e:  # matplotlib optional
        (out / "charts.txt").write_text(f"chart generation failed: {e}")
    return report


def _charts(report: dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, (title, rep) in zip(axes, [("Bracket A: tools ablation", report["main"]), ("Bracket B: strategies", report["strategies"])], strict=True):
        rows = rep["table"]
        names = [r["agent"].replace("llm:mock:", "llm:") for r in rows]
        ax.bar(names, [r["win_rate"] for r in rows], label="win rate")
        ax.bar(names, [r["false_accusation_rate"] for r in rows], alpha=0.5, label="false-accusation rate")
        ax.set_title(title)
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=20, labelsize=8)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)

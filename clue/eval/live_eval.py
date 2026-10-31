"""Live LLM evaluation runner: tool ablation + ponder brackets with paired seeds, Wilson CIs, cost cap.

Brackets (each LLM variant plays the SAME seeds against the same opponents => paired comparison):
  ablation: tool_mode in {precomputed, native, none}
  ponder:   native tool mode with ponder off / on
Results are written incrementally to <out>/live_<bracket>.json so a budget stop still leaves usable data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clue.agents.llm_client import GLOBAL_COST, BudgetExceeded, LLMConnection, configure_budget
from clue.eval.stats import wilson
from clue.eval.tournament import markdown_table, run_tournament
from clue.manager import PlayerSpec
from clue.rules import GameConfig

OPPONENTS = [PlayerSpec(id="P2", kind="baseline", bot="expert"), PlayerSpec(id="P3", kind="baseline", bot="heuristic")]


def _variant(model: str, strategy: str, tool_mode: str, profile: str) -> PlayerSpec:
    return PlayerSpec(id="P1", kind="llm", model=model, strategy=strategy, tools=tool_mode != "none", tool_mode=tool_mode, prompt_profile=profile)


def run_live_eval(
    model: str,
    games: int,
    seed: int = 0,
    out_dir: str = "eval/live",
    max_usd: float | None = 0.25,
    provider: str = "openrouter",
    brackets: tuple[str, ...] = ("ablation", "ponder"),
    strategy: str = "strategies/bayesian_probabilist.md",
    profile: str = "compact",
    verbose: bool = True,
    workers: int = 1,
    connection: LLMConnection | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    configure_budget(max_usd)
    cfg = GameConfig(num_players=3)
    report: dict[str, Any] = {"model": model, "games": games, "seed": seed, "brackets": {}}
    plan: list[tuple[str, str, dict[str, Any]]] = []
    if "ablation" in brackets:
        for tm in ("precomputed", "native", "none"):
            plan.append(("ablation", tm, {"tool_mode": tm, "ponder": False}))
    if "ponder" in brackets:
        for pd in (False, True):
            plan.append(("ponder", f"native{'+ponder' if pd else ''}", {"tool_mode": "native", "ponder": pd}))
    stopped = None
    for bracket, name, kw in plan:
        spec = _variant(model, strategy, kw["tool_mode"], profile)
        partial: list[dict[str, Any]] = []

        def _save(rec: dict[str, Any], _b: str = bracket, _n: str = name, _p: list[dict[str, Any]] = partial) -> None:
            _p.append(rec)
            (out / f"live_{_b}_{_n}.partial.json").write_text(json.dumps({"games": _p, "cost": GLOBAL_COST.summary()}, indent=1))

        try:
            rep = run_tournament(
                [spec, *OPPONENTS], games, seed=seed, config=cfg, provider=provider, rotate_seats=True, verbose=verbose, ponder=kw["ponder"], on_game=_save, workers=workers, connection=connection
            )
        except BudgetExceeded as e:
            stopped = f"{bracket}/{name}: {e}"
            rep = _from_partial(partial, spec.label())
        row = next((r for r in rep["table"] if r["agent"] == spec.label()), None)
        report["brackets"].setdefault(bracket, {})[name] = {
            "label": spec.label(),
            "table": rep["table"],
            "curves": rep.get("curves", {}),
            "fingerprints": rep.get("fingerprints", {}),
            "llm_stats": _aggregate_llm(rep["results"], spec.label()),
            "wins": row["wins"] if row else 0,
            "games": row["games"] if row else len(rep["results"]),
            "results": [{k: v for k, v in r.items() if k in ("seed", "winner_label", "turns")} for r in rep["results"]],
        }
        report["cost"] = GLOBAL_COST.summary()
        (out / "live_report.json").write_text(json.dumps(report, indent=1))
        if stopped:
            break
    report["stopped"] = stopped
    report["cost"] = GLOBAL_COST.summary()
    (out / "live_report.json").write_text(json.dumps(report, indent=1))
    (out / "live_report.md").write_text(render_markdown(report))
    return report


def _from_partial(partial: list[dict[str, Any]], label: str) -> dict[str, Any]:
    wins = sum(1 for r in partial if r.get("winner_label") == label)
    return {
        "table": [{"agent": label, "games": len(partial), "wins": wins, "win_rate": round(wins / max(1, len(partial)), 3), "false_accusation_rate": None, "illegal_attempts": None}],
        "results": partial,
    }


def _aggregate_llm(results: list[dict[str, Any]], label: str) -> dict[str, Any]:
    keys = ("calls", "valid_first_try", "retries", "fallbacks", "native_tool_calls", "ponder_rounds", "prompt_tokens", "completion_tokens", "cost_usd")
    agg: dict[str, float] = dict.fromkeys(keys, 0.0)
    n = 0
    for r in results:
        st = (r.get("llm") or {}).get(label)
        if not st:
            continue
        n += 1
        for k in keys:
            agg[k] += float(st.get(k, 0) or 0)
    if n == 0:
        return {}
    calls = max(1.0, agg["calls"])
    return {
        "games": n,
        "calls_per_game": round(agg["calls"] / n, 1),
        "valid_json_first_try": round(agg["valid_first_try"] / calls, 3),
        "fallback_rate": round(agg["fallbacks"] / calls, 3),
        "native_tool_calls_per_game": round(agg["native_tool_calls"] / n, 1),
        "ponder_rounds_per_game": round(agg["ponder_rounds"] / n, 1),
        "prompt_tokens_per_game": round(agg["prompt_tokens"] / n),
        "completion_tokens_per_game": round(agg["completion_tokens"] / n),
        "usd_per_game": round(agg["cost_usd"] / n, 5),
    }


def render_markdown(report: dict[str, Any]) -> str:
    md = [f"# Live evaluation — `{report['model']}`", f"{report['games']} paired seeds per variant, 3 players (LLM vs baseline:expert + baseline:heuristic, seats shuffled per seed).", ""]
    for bracket, variants in report["brackets"].items():
        md.append(f"## Bracket: {bracket}")
        md.append("| variant | games | wins | win rate [Wilson 95%] | valid JSON 1st try | fallbacks | tool calls/game | ponder rounds/game | prompt tok/game | $/game |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for name, v in variants.items():
            lo, hi = wilson(v["wins"], v["games"])
            st = v.get("llm_stats") or {}
            md.append(
                f"| {name} | {v['games']} | {v['wins']} | {v['wins'] / max(1, v['games']):.2f} [{lo:.2f}, {hi:.2f}] | {st.get('valid_json_first_try', '—')} | {st.get('fallback_rate', '—')} | "
                f"{st.get('native_tool_calls_per_game', '—')} | {st.get('ponder_rounds_per_game', '—')} | {st.get('prompt_tokens_per_game', '—')} | {st.get('usd_per_game', '—')} |"
            )
        # paired seed table
        names = list(variants)
        seeds = sorted({r["seed"] for v in variants.values() for r in v["results"]})
        if seeds:
            md.append("")
            md.append("Per-seed winners (paired): " + ", ".join(names))
            md.append("| seed | " + " | ".join(names) + " |")
            md.append("|---|" + "---|" * len(names))
            for sd in seeds:
                cells = []
                for n in names:
                    r = next((x for x in variants[n]["results"] if x["seed"] == sd), None)
                    cells.append("—" if r is None else ("**LLM**" if r["winner_label"] == variants[n]["label"] else str(r["winner_label"]).replace("baseline:", "")))
                md.append(f"| {sd} | " + " | ".join(cells) + " |")
        for name, v in variants.items():
            if v.get("table") and len(v["table"]) > 1 and "win_ci95" in v["table"][0]:
                md.append("")
                md.append(f"Full table — {name}:")
                md.append(markdown_table({"table": v["table"]}))
        md.append("")
    md.append(f"Cost: `{report.get('cost')}`" + (f" — **stopped early**: {report['stopped']}" if report.get("stopped") else ""))
    return "\n".join(md)

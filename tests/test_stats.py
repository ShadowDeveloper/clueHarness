"""Evaluation statistics + instrumented tournament output."""

from __future__ import annotations

from pathlib import Path

import pytest

from clue.agents.factory import parse_players_arg
from clue.eval.live_eval import render_markdown
from clue.eval.stats import candidate_curve, fingerprint, paired_comparison, wilson
from clue.eval.tournament import markdown_table, run_tournament


def test_wilson_interval_properties() -> None:
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson(10, 10)[1] == 1.0 and wilson(0, 10)[0] == 0.0
    a, b = wilson(50, 100)
    assert b - a < hi - lo  # narrower with more games


def test_paired_sign_test() -> None:
    res = [{"winner_label": "A"}] * 7 + [{"winner_label": "B"}] * 1 + [{"winner_label": "C"}] * 4
    out = paired_comparison(res, "A", "B")
    assert out["a_wins"] == 7 and out["b_wins"] == 1
    assert out["p_value"] == pytest.approx(0.0703, abs=1e-3)  # 2 * P(X<=1 | n=8) = 2*9/256
    assert paired_comparison([], "A", "B")["p_value"] == 1.0


def test_candidate_curve_and_fingerprint() -> None:
    cc = candidate_curve({"x": [[100, 50, 1], [80, 1]]})
    assert cc["x"] == [90.0, 25.5, 1.0]
    fp = fingerprint([{"suggestions": 4, "turn_solved": 10, "turn_accused": 10, "n_at_accusation": 1}, {"suggestions": 6, "turn_solved": None, "turn_accused": 12, "n_at_accusation": 3}])
    assert fp["solved_rate"] == 0.5 and fp["premature_accusation_rate"] == 0.5 and fp["suggestions_mean"] == 5.0


def test_tournament_emits_ci_curves_fingerprints() -> None:
    specs = parse_players_arg("baseline:expert,baseline,baseline")
    rep = run_tournament(specs, 2, seed=1)
    assert all("win_ci95" in r for r in rep["table"])
    assert set(rep["curves"]) == {"baseline:expert", "baseline:heuristic"}
    assert rep["fingerprints"]["baseline:expert"]["accusation_rate"] <= 1.0
    assert any(p["a"] == "baseline:expert" or p["b"] == "baseline:expert" for p in rep["pairwise"])
    md = markdown_table(rep)
    assert "[" in md and "win_ci95" not in md.splitlines()[0]
    fake = {
        "model": "m",
        "games": 2,
        "seed": 0,
        "brackets": {
            "ablation": {
                "native": {"label": "llm:m", "wins": 1, "games": 2, "results": [{"seed": 0, "winner_label": "llm:m"}, {"seed": 1, "winner_label": "baseline:expert"}], "llm_stats": {}, "table": []}
            }
        },
        "cost": {},
    }
    out = render_markdown(fake)
    assert "**LLM**" in out and "expert" in out


def test_parallel_tournament_matches_sequential() -> None:
    specs = parse_players_arg("baseline:expert,baseline,baseline")
    a = run_tournament(specs, 2, seed=21, workers=1)
    b = run_tournament(specs, 2, seed=21, workers=2)
    assert [r["winner_label"] for r in a["results"]] == [r["winner_label"] for r in b["results"]]
    assert a["table"] == b["table"] and a["curves"] == b["curves"]


def test_parallel_tournament_threads_with_shared_client_and_all_cores() -> None:
    """LLM seats with an explicit shared client run in a thread pool; workers=0 means all cores; results identical."""
    from clue.agents.llm_client import MockLLMClient
    from clue.eval.tournament import resolve_workers

    assert resolve_workers(0) >= 1 and resolve_workers(3) == 3
    specs = parse_players_arg("llm:aggressive,baseline,baseline")
    seen: list[int] = []
    a = run_tournament(specs, 3, seed=31, client=MockLLMClient(), workers=1)
    b = run_tournament(specs, 3, seed=31, client=MockLLMClient(), workers=0, on_game=lambda r: seen.append(r["seed"]))
    assert sorted(seen) == [31, 32, 33]
    assert [r["winner_label"] for r in a["results"]] == [r["winner_label"] for r in b["results"]]
    assert [r["seed"] for r in b["results"]] == [31, 32, 33]  # aggregated in seed order even if finished out of order
    assert a["table"] == b["table"]


def test_parallel_tournament_budget_stop_cancels_remaining(tmp_path: Path) -> None:
    from clue.agents.llm_client import BudgetExceeded, MockLLMClient

    class Broke(MockLLMClient):
        def complete(self, *a, **k):  # type: ignore[no-untyped-def]
            raise BudgetExceeded("cap")

    specs = parse_players_arg("llm:aggressive,baseline,baseline")
    done: list[int] = []
    with pytest.raises(BudgetExceeded):
        run_tournament(specs, 4, seed=1, client=Broke(), workers=2, on_game=lambda r: done.append(r["seed"]))
    # LLM agent falls back to heuristics on client errors... unless the error is BudgetExceeded, which must propagate
    assert done == []

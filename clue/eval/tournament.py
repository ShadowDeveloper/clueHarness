"""Batch tournament runner: N games, stats per agent label, ELO, CSV/markdown reports."""

from __future__ import annotations

import csv
import os
import random
import statistics
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from clue.agents.factory import make_agent
from clue.agents.llm_client import LLMClient
from clue.manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.rules import GameConfig
from clue.tools.solver import solve


class _Probe:
    """Per-game instrumentation: candidate-count curve at each of a player's turn starts + behavioural counters."""

    def __init__(self, gm: GameManager) -> None:
        self.gm = gm
        self.players = gm.player_ids()
        self.curves: dict[str, list[int]] = {p: [] for p in self.players}
        self.turn_solved: dict[str, int | None] = dict.fromkeys(self.players)
        self.turn_accused: dict[str, int | None] = dict.fromkeys(self.players)
        self.n_at_accusation: dict[str, int | None] = dict.fromkeys(self.players)
        self.passages: dict[str, int] = dict.fromkeys(self.players, 0)
        self.rooms: dict[str, set[str]] = {p: set() for p in self.players}
        self.own_in_sugg: dict[str, int] = dict.fromkeys(self.players, 0)

    def __call__(self, gm: GameManager, evs: list[dict[str, Any]]) -> None:
        for ev in evs:
            t, who, turn = ev.get("type"), str(ev.get("player")), int(ev.get("turn", 0))
            if t == "turn_start" and who in self.curves:
                n = len(solve(gm.notebooks[who], self.players).combos)
                self.curves[who].append(n)
                if n == 1 and self.turn_solved[who] is None:
                    self.turn_solved[who] = turn
            elif t == "accuse" and who in self.curves:
                self.turn_accused[who] = turn
                n = len(solve(gm.notebooks[who], self.players).combos)
                self.n_at_accusation[who] = n
                if n == 1 and self.turn_solved[who] is None:
                    self.turn_solved[who] = turn  # solved mid-turn (suggest -> shown card -> accuse)
            elif t == "passage" and who in self.passages:
                self.passages[who] += 1
            elif t == "suggest" and who in self.rooms:
                self.rooms[who].add(str(ev.get("room")))
                hand = set(gm.state.player(who).hand)
                self.own_in_sugg[who] += sum(1 for c in (ev.get("suspect"), ev.get("weapon"), ev.get("room")) if c in hand)

    def per_player(self, pid: str, s: dict[str, Any]) -> dict[str, Any]:
        return {
            "suggestions": s["suggestions"].get(pid, 0),
            "turns_alive": len(self.curves[pid]),
            "turn_solved": self.turn_solved[pid],
            "turn_accused": self.turn_accused[pid],
            "n_at_accusation": self.n_at_accusation[pid],
            "passages": self.passages[pid],
            "rooms_visited": len(self.rooms[pid]),
            "own_cards_in_suggestions": self.own_in_sugg[pid],
        }


def _elo_update(ratings: dict[str, float], winner: str | None, players: list[str], k: float = 24.0) -> None:
    """Multiplayer ELO: pairwise updates between the winner and each loser (draw -> no change)."""
    if winner is None:
        return
    for p in players:
        if p == winner:
            continue
        ea = 1 / (1 + 10 ** ((ratings[p] - ratings[winner]) / 400))
        ratings[winner] += k * (1 - ea)
        ratings[p] -= k * (1 - ea)


def _play_one(args: tuple[list[dict[str, Any]], int, dict[str, Any] | None, str | None, bool, bool, str | None, bool], client: LLMClient | None = None) -> dict[str, Any]:
    """Play one tournament game and return its record. Called directly, from a thread (live LLM) or from a worker process
    (offline: args are plain dicts so they pickle; `client` is then None and each process builds its own via make_agent)."""
    spec_dicts, gseed, cfg_dict, provider, rotate_seats, ponder, replay_dir, probe = args
    specs = [PlayerSpec(**d) for d in spec_dicts]
    config = GameConfig(**cfg_dict) if cfg_dict else None
    order = list(specs)
    if rotate_seats:  # shuffle seat order per game (seeded) so neither absolute nor relative seat order favours a label
        random.Random(gseed * 7919 + 17).shuffle(order)
    gspecs = [s.model_copy(update={"id": f"P{i + 1}"}) for i, s in enumerate(order)]
    lab_of = {s.id: s.label() for s in gspecs}
    gm = GameManager.create(gspecs, seed=gseed, config=config)
    agents = {s.id: make_agent(s, seed=gseed + i, client=client, provider=provider) for i, s in enumerate(gspecs)}
    pr = _Probe(gm) if probe else None
    run_game(gm, agents, on_events=pr, ponder=ponder)
    s = gm.summary()
    if replay_dir:
        gm.write_replay(Path(replay_dir) / f"game_{gseed}.jsonl")
    rec: dict[str, Any] = {
        "seed": gseed,
        "summary": s,
        "lab_of": lab_of,
        "winner": s["winner"],
        "winner_label": lab_of.get(s["winner"] or "", None),
        "turns": s["turns"],
        "solution": s["solution"],
        "seats": lab_of,
    }
    if pr is not None:
        rec["curves"] = {lab_of[p]: pr.curves[p] for p in lab_of}
        rec["fingerprints"] = {lab_of[p]: pr.per_player(p, s) for p in lab_of}
    rec["llm"] = {lab_of[p]: {**a.stats, "cost_usd": round(getattr(a, "cost_usd", 0.0), 5)} for p, a in agents.items() if hasattr(a, "stats") and a.kind == "llm"}
    return rec


def resolve_workers(workers: int) -> int:
    """0 / negative -> one worker per CPU core."""
    return workers if workers > 0 else max(1, os.cpu_count() or 1)


def _needs_live_llm(specs: list[PlayerSpec], provider: str | None) -> bool:
    """True when at least one seat will talk to a real (non-mock) LLM -> use threads, not processes."""
    if not any(s.kind == "llm" for s in specs):
        return False
    prov = (provider or os.getenv("CLUE_LLM_PROVIDER") or "mock").lower()
    return prov != "mock"


def run_tournament(
    specs: list[PlayerSpec],
    games: int,
    seed: int = 0,
    config: GameConfig | None = None,
    client: LLMClient | None = None,
    provider: str | None = None,
    rotate_seats: bool = True,
    replay_dir: str | Path | None = None,
    verbose: bool = False,
    ponder: bool = False,
    probe: bool = True,
    on_game: Any = None,
    workers: int = 1,
) -> dict[str, Any]:
    """Play `games` games, up to `workers` at a time (0 = all cores).

    Offline/mock seats run in a **process pool** (CPU-bound solver work). Games with a live LLM seat, or an explicit
    shared `client`, run in a **thread pool** instead: they are HTTP-bound, and the spend cap (`CostTracker`) and the
    response cache stay shared and lock-protected in one process. Results are identical to a sequential run regardless of
    `workers` (each game is seeded by `seed + i`; records are aggregated in seed order). `on_game` fires as games finish.
    If the budget cap trips, remaining games are cancelled and `BudgetExceeded` propagates after `on_game` saw the
    completed ones.
    """
    workers = min(resolve_workers(workers), max(1, games))
    labels = {s.id: s.label() for s in specs}
    jobs = [([s.model_dump() for s in specs], seed + g, config.model_dump() if config else None, provider, rotate_seats, ponder, str(replay_dir) if replay_dir else None, probe) for g in range(games)]
    by_seed: dict[int, dict[str, Any]] = {}

    def _done(rec: dict[str, Any], n_done: int) -> None:
        by_seed[rec["seed"]] = rec
        if verbose:
            print(f"game {n_done}/{games} seed={rec['seed']} winner={rec['winner_label']} turns={rec['turns']}", flush=True)
        if on_game:
            on_game(rec)

    if workers <= 1:
        for i, job in enumerate(jobs):
            _done(_play_one(job, client), i + 1)
    else:
        threaded = client is not None or _needs_live_llm(specs, provider)
        pool: Executor = ThreadPoolExecutor(max_workers=workers) if threaded else ProcessPoolExecutor(max_workers=workers)
        with pool as ex:
            futs = [ex.submit(_play_one, job, client) if threaded else ex.submit(_play_one, job) for job in jobs]
            try:
                for n, fut in enumerate(as_completed(futs), 1):
                    _done(fut.result(), n)
            except BaseException:
                for f in futs:
                    f.cancel()
                raise
    recs = [by_seed[s] for s in sorted(by_seed)]
    return aggregate(recs, labels, games=games, seed=seed)


def aggregate(recs: list[dict[str, Any]], labels: dict[str, str] | None = None, games: int | None = None, seed: int = 0) -> dict[str, Any]:
    """Turn per-game records (as produced by `_play_one`) into the tournament report: per-label table, ELO, pairwise,
    candidate curves, fingerprints. Pure - usable on a partial list for live progress. Records are not mutated."""
    labs = set((labels or {}).values()) | {lab for r in recs for lab in r["seats"].values()}
    per: dict[str, dict[str, Any]] = {lab: {"games": 0, "wins": 0, "false_acc": 0, "suggestions": 0, "turns_to_win": [], "illegal": 0, "eliminated": 0} for lab in labs}
    ratings = {lab: 1000.0 for lab in per}
    results = []
    for rec in recs:
        rec = dict(rec)
        s, lab_of = rec.pop("summary"), rec.pop("lab_of")
        for pid, lab in lab_of.items():
            d = per[lab]
            d["games"] += 1
            d["suggestions"] += s["suggestions"].get(pid, 0)
            d["illegal"] += s["illegal_attempts"].get(pid, 0)
            if pid in s["false_accusations"]:
                d["false_acc"] += 1
            if pid in s["eliminated"]:
                d["eliminated"] += 1
            if s["winner"] == pid:
                d["wins"] += 1
                d["turns_to_win"].append(s["turns"])
        # ELO over labels (if two seats share a label the update is between identical ratings -> skip self pairs)
        wl = lab_of.get(s["winner"] or "", None)
        if wl:
            _elo_update(ratings, wl, [lab_of[p] for p in lab_of if lab_of[p] != wl] + [wl])
        results.append(rec)
    table = []
    for lab, d in per.items():
        table.append(
            {
                "agent": lab,
                "games": d["games"],
                "wins": d["wins"],
                "win_rate": round(d["wins"] / max(1, d["games"]), 3),
                "false_accusation_rate": round(d["false_acc"] / max(1, d["games"]), 3),
                "avg_turns_to_win": round(statistics.mean(d["turns_to_win"]), 1) if d["turns_to_win"] else None,
                "avg_suggestions_per_game": round(d["suggestions"] / max(1, d["games"]), 2),
                "illegal_attempts": d["illegal"],
                "elo": round(ratings[lab]),
            }
        )
    table.sort(key=lambda r: -r["win_rate"])
    from clue.eval.stats import candidate_curve, fingerprint, group_curves, summarise

    extra = summarise(results, table)
    fps: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        for lab, fp in (r.get("fingerprints") or {}).items():
            fps.setdefault(lab, []).append(fp)
    return {
        "games": games if games is not None else len(results),
        "seed": seed,
        "table": table,
        "results": results,
        "pairwise": extra["pairwise"],
        "curves": candidate_curve(group_curves(results)),
        "fingerprints": {lab: fingerprint(v) for lab, v in fps.items()},
    }


def write_csv(report: dict[str, Any], path: str | Path) -> None:
    rows = [{k: (f"{v[0]}-{v[1]}" if isinstance(v, list) else v) for k, v in r.items()} for r in report["table"]]
    with Path(path).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def markdown_table(report: dict[str, Any]) -> str:
    rows = report["table"]
    cols = [c for c in rows[0].keys() if c != "win_ci95"]
    if "win_ci95" in rows[0]:
        rows = [{**r, "win_rate": f"{r['win_rate']} [{r['win_ci95'][0]}, {r['win_ci95'][1]}]"} for r in rows]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)

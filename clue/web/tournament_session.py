"""A tournament running in a background thread with live, incrementally aggregated results."""

from __future__ import annotations

import threading
import time
from typing import Any

from clue.agents.llm_client import GLOBAL_COST, BudgetExceeded
from clue.eval.tournament import aggregate, run_tournament
from clue.manager.game_manager import PlayerSpec
from clue.rules import GameConfig


class TournamentSession:
    def __init__(self, tid: str, specs: list[PlayerSpec], games: int, seed: int, workers: int, ponder: bool, provider: str | None, config: GameConfig | None, probe: bool = True) -> None:
        self.id = tid
        self.specs = specs
        self.games = games
        self.seed = seed
        self.workers = workers
        self.ponder = ponder
        self.provider = provider
        self.config = config
        self.probe = probe
        self.status = "running"
        self.started = time.time()
        self.finished_at: float | None = None
        self.error: str | None = None
        self.recs: list[dict[str, Any]] = []
        self.report: dict[str, Any] | None = None
        self._cancel = False
        self._lock = threading.Lock()
        self._subs: dict[int, Any] = {}
        self._sub_seq = 0
        self.thread = threading.Thread(target=self._run, name=f"tournament-{tid}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _on_game(self, rec: dict[str, Any]) -> None:
        with self._lock:
            self.recs.append(rec)
            n = len(self.recs)
        if self._cancel:
            raise BudgetExceeded("cancelled by user")  # reuses the runner's cooperative cancellation path
        self._broadcast({"type": "progress", "done": n, "games": self.games, "seed": rec["seed"], "winner_label": rec["winner_label"], "turns": rec["turns"]})

    def _run(self) -> None:
        try:
            self.report = run_tournament(
                self.specs, self.games, seed=self.seed, config=self.config, provider=self.provider, ponder=self.ponder, probe=self.probe, on_game=self._on_game, workers=self.workers
            )
            self.status = "finished"
        except BudgetExceeded as e:
            self.status = "cancelled"
            self.error = str(e)
        except Exception as e:
            self.status = "error"
            self.error = str(e)
        self.finished_at = time.time()
        self._broadcast({"type": "done", **self.snapshot()})

    def cancel(self) -> None:
        self._cancel = True

    def current_report(self) -> dict[str, Any] | None:
        if self.report is not None:
            return self.report
        with self._lock:
            recs = list(self.recs)
        if not recs:
            return None
        rep = aggregate(recs, {s.id: s.label() for s in self.specs}, games=self.games, seed=self.seed)
        rep["results"] = [{k: v for k, v in r.items() if k not in ("curves", "fingerprints")} for r in rep["results"]]
        return rep

    def snapshot(self) -> dict[str, Any]:
        rep = self.current_report()
        if rep is not None and self.report is not None:
            rep = dict(rep)
            rep["results"] = [{k: v for k, v in r.items() if k not in ("curves", "fingerprints")} for r in rep["results"]]
        return {
            "id": self.id,
            "status": self.status,
            "games": self.games,
            "done": len(self.recs),
            "seed": self.seed,
            "players": [s.label() for s in self.specs],
            "started": self.started,
            "finished_at": self.finished_at,
            "error": self.error,
            "report": rep,
            "cost": GLOBAL_COST.summary(),
        }

    def subscribe(self, cb: Any) -> int:
        with self._lock:
            self._sub_seq += 1
            self._subs[self._sub_seq] = cb
            return self._sub_seq

    def unsubscribe(self, sid: int) -> None:
        with self._lock:
            self._subs.pop(sid, None)

    def _broadcast(self, frame: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subs.values())
        for cb in subs:
            try:
                cb(frame)
            except Exception:
                pass

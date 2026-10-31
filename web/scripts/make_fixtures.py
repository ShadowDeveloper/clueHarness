#!/usr/bin/env python3
"""Regenerate web/src/analysis/__tests__/fixtures.json from the authoritative Python solver.

The TypeScript analysis engine (web/src/analysis) is a port of clue/tools/{solver,deduction,analyst}.py
so the analyst page can run fully client-side (e.g. on GitHub Pages). This script freezes Python results
for a set of sessions; `npm test` asserts the port reproduces them. Rerun after changing the Python
solver:  python web/scripts/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from clue.tools.analyst import AnalysisSession, analyze, build_notebook, default_hand_sizes  # noqa: E402
from clue.tools.solver import solve  # noqa: E402

SESSIONS: dict[str, dict] = {
    "fresh_hand_only": {
        "edition": "classic",
        "players": ["P1", "P2", "P3"],
        "me": "P1",
        "my_cards": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick", "Wrench"],
        "faceup": [],
        "observations": [],
    },
    "demo_midgame": {
        "edition": "classic",
        "players": ["Me", "Alice", "Bob", "Cara"],
        "me": "Me",
        "my_cards": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
        "faceup": [],
        "observations": [
            {"type": "suggestion", "suggester": "Me", "suspect": "Prof. Plum", "weapon": "Dagger", "room": "Lounge", "disprover": "Bob", "shown_card": "Dagger"},
            {"type": "suggestion", "suggester": "Alice", "suspect": "Mrs. Peacock", "weapon": "Revolver", "room": "Kitchen", "disprover": "Cara"},
            {"type": "suggestion", "suggester": "Bob", "suspect": "Col. Mustard", "weapon": "Lead Pipe", "room": "Ballroom", "disprover": None},
            {"type": "fact", "player": "Alice", "card": "Library", "has": True},
        ],
    },
    "solved_deal": {
        "edition": "classic",
        "players": ["Me", "Alice", "Bob", "Cara"],
        "me": "Me",
        "my_cards": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
        "faceup": [],
        "observations": (
            [{"type": "fact", "player": "Alice", "card": c, "has": True} for c in ["Col. Mustard", "Dagger", "Lounge", "Library", "Mrs. White"]]
            + [{"type": "fact", "player": "Bob", "card": c, "has": True} for c in ["Lead Pipe", "Kitchen", "Ballroom", "Mr. Green"]]
            + [{"type": "fact", "player": "Cara", "card": c, "has": True} for c in ["Revolver", "Conservatory", "Billiard Room", "Prof. Plum"]]
        ),
    },
    "modern_faceup_sixplayers": {
        "edition": "modern",
        "players": ["A", "B", "C", "D", "E", "F"],
        "me": "C",
        "my_cards": ["Dr. Orchid", "Wrench", "Library"],
        "faceup": [],
        "observations": [
            {"type": "suggestion", "suggester": "A", "suspect": "Miss Scarlet", "weapon": "Rope", "room": "Hall", "disprover": "D"},
            {"type": "suggestion", "suggester": "B", "suspect": "Miss Scarlet", "weapon": "Rope", "room": "Study", "disprover": "E"},
            {"type": "suggestion", "suggester": "C", "suspect": "Mr. Green", "weapon": "Revolver", "room": "Kitchen", "disprover": "F", "shown_card": "Revolver"},
            {"type": "suggestion", "suggester": "D", "suspect": "Mrs. Peacock", "weapon": "Candlestick", "room": "Ballroom", "disprover": None},
            {"type": "fact", "player": "B", "card": "Lounge", "has": False},
        ],
    },
    "contradiction": {
        "edition": "classic",
        "players": ["Me", "Alice", "Bob", "Cara"],
        "me": "Me",
        "my_cards": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
        "faceup": [],
        "observations": [
            {"type": "suggestion", "suggester": "Me", "suspect": "Prof. Plum", "weapon": "Dagger", "room": "Lounge", "disprover": "Bob", "shown_card": "Dagger"},
            {"type": "fact", "player": "Alice", "card": "Prof. Plum", "has": True},
        ],
    },
}


def freeze(name: str, raw: dict) -> dict:
    session = AnalysisSession.model_validate(raw)
    report = analyze(session)
    nb = build_notebook(session)
    sizes = default_hand_sizes(session)
    sol = solve(nb, session.players, sizes, session.edition)
    total = sol.n_assignments or 1
    return {
        "session": raw,
        "expected": {
            "hand_sizes": sizes,
            "ok": report["ok"],
            "consistent": report["consistent"],
            "exact": sol.exact,
            "n_possible": len(sol.combos),
            "combos": {" | ".join(c): round(n / total, 6) for c, n in sorted(sol.combos.items())},
            "card_probs": {c: round(p, 6) for c, p in sorted(sol.card_probs.items())},
            "holder_probs": {c: {h: round(p, 6) for h, p in sorted(probs.items())} for c, probs in sorted(sol.holder_probs.items())},
            "certain_holder": dict(sorted(sol.certain_holder.items())),
            "deductions": report["deductions"] if report["ok"] else [],
            "best": report["solution"]["best"] if report["ok"] else None,
            "best_prob": report["solution"]["best_prob"] if report["ok"] else 0,
            "accuse": report["guide"]["accusal"]["accuse"] if report["ok"] else False,
            "suggestions": [{"room": s["room"], "score": s["score"]} for s in report["guide"]["suggestions"]] if report["ok"] else [],
            "threat": report["threat"] if report["ok"] else None,
            "advice_first": report["guide"]["advice"][0] if report["ok"] and report["guide"]["advice"] else None,
        },
    }


def main() -> None:
    out = {name: freeze(name, raw) for name, raw in SESSIONS.items()}
    dest = Path(__file__).resolve().parents[1] / "src" / "analysis" / "__tests__" / "fixtures.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {dest} ({len(out)} fixtures)")


if __name__ == "__main__":
    main()

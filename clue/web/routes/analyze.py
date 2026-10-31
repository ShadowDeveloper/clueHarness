"""Stateless analyst endpoint: POST a hand-entered session, get the full solver + coach report.

The browser page (web/src/pages/Analyze.tsx) normally runs a client-side TypeScript port of the same
math so it also works on the static GitHub Pages build; this endpoint provides the authoritative
Python result for API users and for cross-checking the port.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from clue.tools.analyst import AnalysisSession, analyze

router = APIRouter()


@router.post("/analyze")
def analyze_session(session: AnalysisSession, threshold: float = Query(0.9, ge=0.0, le=1.0)) -> dict[str, Any]:
    """Validate the session and return probabilities, hard deductions, opponent threat, and the guide."""
    return analyze(session, accuse_threshold=threshold)

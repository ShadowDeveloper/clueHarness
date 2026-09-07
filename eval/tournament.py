"""Thin entrypoint: `python eval/tournament.py --games 50` (delegates to clue.eval)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clue.__main__ import app  # noqa: E402

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "eval", *sys.argv[1:]]
    app()

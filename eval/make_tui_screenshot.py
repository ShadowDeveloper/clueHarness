"""Render a headless TUI screenshot (SVG + plain text) into docs/ for documentation."""

from __future__ import annotations

import asyncio
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402
from textual.widgets import OptionList  # noqa: E402

from clue.agents.baselines import BaselineHeuristicBot  # noqa: E402
from clue.manager import GameManager, PlayerSpec  # noqa: E402
from clue.tui.app import ClueApp, TUIHumanAgent  # noqa: E402


async def main() -> None:
    specs = [PlayerSpec(id="P1", kind="human"), PlayerSpec(id="P2", kind="baseline"), PlayerSpec(id="P3", kind="baseline"), PlayerSpec(id="P4", kind="baseline")]
    gm = GameManager.create(specs, seed=42)
    agents = {"P1": TUIHumanAgent("P1"), **{p: BaselineHeuristicBot(p, i) for i, p in enumerate(["P2", "P3", "P4"], 1)}}
    app = ClueApp(gm, agents, delay=0.0)
    async with app.run_test(size=(170, 48)) as pilot:
        for _ in range(20):
            for _ in range(200):
                if app.req is not None or gm.finished:
                    break
                await asyncio.sleep(0.05)
            if app.mode == "main":
                await pilot.press("r")
                await pilot.pause()
                if app.mode == "main":
                    await pilot.press("e")
            elif app.mode == "move" and _ == 6:
                break  # leave the move picker open for the screenshot
            else:
                ol = app.query_one("#choices", OptionList)
                ids = [str(ol.get_option_at_index(i).id) for i in range(ol.option_count)]
                pref = next((i for i, x in enumerate(ids) if x.startswith("move:") and "," not in x), 0)
                ol.highlighted = pref
                await pilot.click("#b_confirm")
            await pilot.pause()
        await pilot.pause()
        app.save_screenshot("docs/tui_screenshot.svg")
        con = Console(file=io.StringIO(), width=170, height=48, force_terminal=False, color_system=None)
        con.print(app.screen._compositor.render_update(full=True))  # noqa: SLF001
        pathlib.Path("docs/tui_screenshot.txt").write_text(str(con.file.getvalue()))  # type: ignore[attr-defined]
        if app.req:
            app.req.reply.put(None)
        app.exit()


asyncio.run(main())

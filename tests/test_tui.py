"""Headless Textual tests: spectate mode runs to completion; human seat can drive a full game via the UI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from textual.widgets import OptionList

from clue.agents.baselines import BaselineHeuristicBot
from clue.manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.tui.app import ClueApp, TUIHumanAgent

pytestmark = pytest.mark.asyncio


async def _wait(cond, timeout: float = 20.0) -> None:  # type: ignore[no-untyped-def]
    t = 0.0
    while not cond() and t < timeout:
        await asyncio.sleep(0.05)
        t += 0.05
    assert cond(), "timeout"


async def test_spectate_runs_to_completion() -> None:
    specs = [PlayerSpec(id=f"P{i}", kind="baseline") for i in range(1, 4)]
    gm = GameManager.create(specs, seed=3)
    agents = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    app = ClueApp(gm, agents, delay=0.0)
    async with app.run_test(size=(140, 45)) as pilot:
        await _wait(lambda: gm.finished, timeout=60)
        await pilot.pause()
        assert gm.winner is not None or gm.finished
        assert "GAME OVER" in str(app.query_one("#banner").render())


async def test_human_seat_drives_game_via_option_list() -> None:
    specs = [PlayerSpec(id="P1", kind="human"), PlayerSpec(id="P2", kind="baseline"), PlayerSpec(id="P3", kind="baseline")]
    gm = GameManager.create(specs, seed=5)
    human = TUIHumanAgent("P1")
    agents = {"P1": human, "P2": BaselineHeuristicBot("P2", 1), "P3": BaselineHeuristicBot("P3", 2)}
    app = ClueApp(gm, agents, delay=0.0)
    picks = 0
    async with app.run_test(size=(140, 45)) as pilot:
        while not gm.finished and picks < 400:
            await _wait(lambda: app.req is not None or gm.finished, timeout=30)
            if gm.finished:
                break
            if app.mode == "main":
                # buttons/hotkeys: roll if possible, else end turn
                await pilot.press("r")
                await pilot.pause()
                if app.mode == "main":
                    await pilot.press("e")
            else:  # move / card pickers: confirm the first option
                await pilot.click("#b_confirm")
            picks += 1
            await pilot.pause()
        await _wait(lambda: gm.finished, timeout=60)
    assert gm.finished and picks > 0
    assert gm.illegal_attempts.get("P1", 0) == 0


async def test_human_can_build_accusation() -> None:
    specs = [PlayerSpec(id="P1", kind="human"), PlayerSpec(id="P2", kind="baseline"), PlayerSpec(id="P3", kind="baseline")]
    gm = GameManager.create(specs, seed=6)
    human = TUIHumanAgent("P1")
    agents = {"P1": human, "P2": BaselineHeuristicBot("P2", 1), "P3": BaselineHeuristicBot("P3", 2)}
    app = ClueApp(gm, agents, delay=0.0)
    s, w, r = gm.state.solution
    async with app.run_test(size=(140, 45)) as pilot:
        await _wait(lambda: app.req is not None)
        await pilot.press("a")  # accuse hotkey
        await pilot.pause()
        assert app.mode == "pick"
        # exercise Back: pick a suspect, go back, pick again
        ol = app.query_one("#choices", OptionList)
        ol.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app._build["suspect"] is None
        for value in (s, w, r):
            ol = app.query_one("#choices", OptionList)
            idx = next(i for i in range(ol.option_count) if str(ol.get_option_at_index(i).id).endswith(f":{value}"))
            ol.highlighted = idx
            await pilot.click("#b_confirm")
            await pilot.pause()
        await _wait(lambda: gm.finished)
    assert gm.winner == "P1"


async def test_large_board_has_natural_width_and_scrolls_without_wrapping() -> None:
    """The 36-column Large board must not be squeezed through the Classic board's 56-column slot."""
    from textual.containers import ScrollableContainer
    from textual.widgets import Static

    from clue.config import load_yaml_config

    class LayoutApp(ClueApp):
        def _game_loop(self) -> None:
            pass  # Layout-only test: no agents or provider calls.

    cfg, specs, seed, _ = load_yaml_config("strategy_game.yaml")
    gm = GameManager.create(specs, seed=seed, config=cfg)
    app = LayoutApp(gm, {s.id: BaselineHeuristicBot(s.id, i) for i, s in enumerate(specs)}, delay=0.0)
    async with app.run_test(size=(170, 48)) as pilot:
        await pilot.pause(0.05)
        board = app.query_one("#board", ScrollableContainer)
        content = app.query_one("#board_content", Static)
        assert content.outer_size.width == 76
        assert board.outer_size.width == 81  # full grid plus border, padding, and vertical scrollbar
        assert board.max_scroll_x == 0

        await pilot.resize_terminal(140, 45)
        await pilot.pause(0.05)
        assert board.outer_size.width == 72
        assert content.outer_size.width == 76  # overflow scrolls; the text itself is never wrapped
        assert board.max_scroll_x > 0 and board.max_scroll_y > 0

        await pilot.resize_terminal(240, 60)
        await pilot.pause(0.05)
        assert board.outer_size.width == 80
        assert board.max_scroll_x == 0 and board.max_scroll_y == 0
        app.exit()


@pytest.mark.filterwarnings("ignore")
def test_token_glyphs_are_two_cells_wide() -> None:
    from rich.cells import cell_len

    from clue.tui.board_render import TOKEN_EMOJI, token_glyph

    for lab in TOKEN_EMOJI:
        assert cell_len(token_glyph(lab, emoji=True)) == 2
        assert cell_len(token_glyph(lab, emoji=False)) == 2


async def test_coach_mode_is_opt_in_and_not_persisted() -> None:
    """`h` shows solver hints for the human; nothing is written to the human's notebook; a log note records use."""
    specs = [PlayerSpec(id="P1", kind="human"), PlayerSpec(id="P2", kind="baseline"), PlayerSpec(id="P3", kind="baseline")]
    gm = GameManager.create(specs, seed=6)
    human = TUIHumanAgent("P1")
    agents = {"P1": human, "P2": BaselineHeuristicBot("P2", 1), "P3": BaselineHeuristicBot("P3", 2)}
    app = ClueApp(gm, agents, delay=0.0)
    async with app.run_test(size=(140, 45)) as pilot:
        await _wait(lambda: app.req is not None, timeout=30)
        coach = app.query_one("#coach")
        assert not coach.display
        before = gm.notebooks["P1"].model_dump()
        await pilot.press("h")
        await pilot.pause()
        assert coach.display and app.coach
        text = str(coach.render())
        assert "combination(s) still possible" in text and "expert would:" in text
        assert gm.notebooks["P1"].model_dump() == before  # no hard deductions leaked into the notebook
        assert any(r.kind == "agent_note" and r.data.get("summary") == "coach_mode_on" for r in gm.log)
        await pilot.press("h")
        await pilot.pause()
        assert not coach.display
        if app.req is not None:
            app.req.reply.put(None)
        app.exit()


async def test_replay_viewer_steps_and_redacts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from clue.tui.replay_viewer import ReplayApp, ReplayState, load_replay

    specs = [PlayerSpec(id=f"P{i}", kind="baseline", bot="expert" if i == 1 else None) for i in range(1, 4)]
    gm = GameManager.create(specs, seed=4)
    from clue.agents.factory import make_agent
    from clue.manager.runner import run_game

    run_game(gm, {s.id: make_agent(s, seed=4) for s in specs})
    path = gm.write_replay(tmp_path / "g.jsonl")
    recs = load_replay(path)
    rs = ReplayState(recs)
    rs.seek(len(rs.events))
    # board reconstruction matches the final engine state
    assert rs.tokens == gm.state.token_positions and rs.weapons == gm.state.weapon_positions
    rs.seek(3)
    assert rs.idx == 3
    app = ReplayApp(recs, delay=0.1)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("n", "n", "n", "b")
        await pilot.pause()
        assert app.rs.idx == 2
        await pilot.press("G")
        await pilot.pause()
        assert app.rs.idx == len(app.rs.events)
        shown = [ev for ev in app.rs.events if ev.get("type") == "disproved" and "card" in ev]
        assert shown, "omniscient replay carries shown cards"
        await pilot.press("v")  # viewer P1: cards shown between P2 and P3 must be hidden
        await pilot.pause()
        ev = next(e for e in shown if "P1" not in (e.get("player"), e.get("suggester")))
        assert "card" not in app._redact(ev) and app.viewer == "P1"
        await pilot.press("g", "space")
        await pilot.pause(0.5)
        assert app.rs.idx >= 1
        app.exit()


async def test_large_replay_board_uses_same_responsive_scrolling() -> None:
    from textual.containers import ScrollableContainer
    from textual.widgets import Static

    from clue.config import load_yaml_config
    from clue.tui.replay_viewer import ReplayApp

    cfg, specs, seed, _ = load_yaml_config("strategy_game.yaml")
    gm = GameManager.create(specs, seed=seed, config=cfg)
    app = ReplayApp(gm.export_replay())
    async with app.run_test(size=(240, 60)) as pilot:
        await pilot.pause(0.05)
        board = app.query_one("#board", ScrollableContainer)
        assert board.outer_size.width == 80
        assert board.max_scroll_x == 0 and board.max_scroll_y == 0
        await pilot.resize_terminal(100, 45)
        await pilot.pause(0.05)
        assert board.outer_size.width == 60
        assert app.query_one("#board_content", Static).outer_size.width == 76
        assert board.max_scroll_x > 0 and board.max_scroll_y > 0
        app.exit()


async def test_spectator_is_omniscient_and_can_cycle_views() -> None:
    from clue.tui.app import OmniscientView

    specs = [PlayerSpec(id=f"P{i}", kind="baseline") for i in range(1, 4)]
    gm = GameManager.create(specs, seed=11)
    agents = {pid: BaselineHeuristicBot(pid, i) for i, pid in enumerate(gm.player_ids())}
    app = ClueApp(gm, agents, delay=0.0)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.refresh_view()
        assert app.viewer is None and app.query_one("#omni", OmniscientView).display and not app.query_one("#notebook").display
        status = str(app.query_one("#status").render())
        assert "omniscient" in status and all(c in status for c in gm.state.solution)
        await _wait(lambda: gm.finished, timeout=60)
        await pilot.pause()
        # every shown card was written to the log un-redacted
        log_text = "\n".join(str(line) for line in app.query_one("#log").lines)
        shown = [e for e in gm.events if e.type == "disproved" and e.private.get("card")]
        assert shown and all("showed the " in log_text for _ in shown[:1])
        assert "a card to" not in log_text  # no redacted lines at all
        await pilot.press("v")
        await pilot.pause()
        assert app.viewer == "P1" and app.query_one("#notebook").display and "viewing as" in str(app.query_one("#status").render())
        await pilot.press("v", "v", "v")
        await pilot.pause()
        assert app.viewer is None
        app.exit()


async def test_ctrl_s_saves_and_q_checkpoints_mid_game(tmp_path: Path) -> None:
    """ctrl+s writes a resumable checkpoint; q during the human's turn saves, unblocks the loop and exits cleanly."""
    specs = [PlayerSpec(id="P1", kind="human"), PlayerSpec(id="P2", kind="baseline"), PlayerSpec(id="P3", kind="baseline")]
    gm = GameManager.create(specs, seed=5)
    human = TUIHumanAgent("P1")
    agents = {"P1": human, "P2": BaselineHeuristicBot("P2", 1), "P3": BaselineHeuristicBot("P3", 2)}
    cp = tmp_path / "cp.json"
    app = ClueApp(gm, agents, delay=0.0, autosave=str(cp))
    async with app.run_test(size=(140, 45)) as pilot:
        await _wait(lambda: app.req is not None, timeout=30)  # human's first decision pending
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert cp.exists()
        first = GameManager.load(cp)
        assert not first.finished and first.state == gm.state
        # play one human action so the autosave path (after every action) is exercised too
        await pilot.press("r")
        await pilot.pause()
        await _wait(lambda: app.req is not None and app.mode != "main", timeout=30)
        await pilot.click("#b_confirm")
        await pilot.pause()
        await _wait(lambda: app.req is not None and len(gm.events) > len(first.events), timeout=30)
        assert GameManager.load(cp).state != first.state
        await pilot.press("q")
        await _wait(lambda: not app.is_running, timeout=15)
    assert not gm.finished
    saved = GameManager.load(cp)
    assert saved.state == gm.state and saved.replay_hash() == gm.replay_hash()
    # and it resumes to completion with fresh bots
    fresh = {"P1": BaselineHeuristicBot("P1", 0), "P2": BaselineHeuristicBot("P2", 1), "P3": BaselineHeuristicBot("P3", 2)}
    assert set(saved.restore_agents(fresh)) == {"P1", "P2", "P3"}
    run_game(saved, fresh)
    assert saved.finished

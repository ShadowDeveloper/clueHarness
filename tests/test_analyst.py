"""Analyst tool: session -> notebook conversion, report content, web route, and the Textual app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable, Input, OptionList, SelectionList

from clue.rules.cards import rooms, suspects, weapons
from clue.tools.analyst import (
    AnalysisSession,
    FactObservation,
    SuggestionObservation,
    analyze,
    build_notebook,
    default_hand_sizes,
    session_events,
    validate_session,
)
from clue.tui.analyst_app import AnalystApp, observation_label

PLAYERS = ["Me", "Alice", "Bob", "Cara"]
MY_CARDS = ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"]


def demo_session() -> AnalysisSession:
    return AnalysisSession(
        players=list(PLAYERS),
        me="Me",
        my_cards=list(MY_CARDS),
        observations=[
            SuggestionObservation(suggester="Me", suspect="Prof. Plum", weapon="Dagger", room="Lounge", disprover="Bob", shown_card="Dagger"),
            SuggestionObservation(suggester="Alice", suspect="Mrs. Peacock", weapon="Revolver", room="Kitchen", disprover="Cara"),
            SuggestionObservation(suggester="Bob", suspect="Col. Mustard", weapon="Lead Pipe", room="Ballroom", disprover=None),
            FactObservation(player="Alice", card="Library", has=True),
        ],
    )


# ---------------------------------------------------------------- core conversion


def test_session_events_mark_passers_and_disprover() -> None:
    nb = build_notebook(demo_session())
    # Alice sits between Me (suggester) and Bob (disprover): she passed on Plum/Dagger/Lounge
    assert {"Prof. Plum", "Dagger", "Lounge"} <= set(nb.not_held["Alice"])
    # shown card becomes a known holder; my own cards are known too
    assert nb.known_holder["Dagger"] == "Bob"
    assert all(nb.known_holder[c] == "Me" for c in MY_CARDS)
    # Cara disproved Alice without showing us the card -> has_one_of constraint
    assert any(c.player == "Cara" and set(c.cards) == {"Mrs. Peacock", "Revolver", "Kitchen"} for c in nb.has_one_of)
    # nobody disproved Bob's suggestion -> everyone else lacks all three, and it is recorded as unrefuted
    for p in ("Me", "Alice", "Cara"):
        assert {"Col. Mustard", "Lead Pipe", "Ballroom"} <= set(nb.not_held[p])
    assert any(set(c.cards) == {"Col. Mustard", "Lead Pipe", "Ballroom"} for c in nb.unrefuted_suggestions)
    # the fact observation landed
    assert nb.known_holder["Library"] == "Alice"
    # events are the engine vocabulary (consumable by opponent_threat)
    kinds = {e["type"] for e in session_events(demo_session())}
    assert kinds == {"suggest", "cannot_disprove", "disproved", "no_one_disproved"}


def test_default_hand_sizes_pin_my_seat() -> None:
    sizes = default_hand_sizes(demo_session())
    assert sizes["Me"] == len(MY_CARDS) and sum(sizes.values()) == 18
    s = demo_session()
    s.faceup = ["Wrench", "Lounge"]
    s.my_cards = ["Miss Scarlet", "Rope", "Hall", "Study"]
    sizes = default_hand_sizes(s)
    assert sizes["Me"] == 4 and sum(sizes.values()) == 16
    s.hand_sizes = {"Me": 4, "Alice": 4, "Bob": 4, "Cara": 4}
    assert default_hand_sizes(s) == s.hand_sizes


def test_validate_session_catches_mistakes() -> None:
    assert validate_session(demo_session()) == []
    bad = AnalysisSession(players=["A", "A", "B"], me="X", my_cards=["Nope"], faceup=["Nope2"])
    errs = "\n".join(validate_session(bad))
    for frag in ("unique", "your seat", "my_cards", "faceup"):
        assert frag in errs
    s = demo_session()
    s.observations.append(SuggestionObservation(suggester="Me", suspect="Rope", weapon="Dagger", room="Hall", disprover="Me", shown_card="Study"))
    errs = "\n".join(validate_session(s))
    assert "not a classic-edition suspect" in errs and "cannot disprove their own" in errs and "not one of the three" in errs
    s2 = demo_session()
    s2.hand_sizes = {p: 1 for p in PLAYERS}
    assert any("sum to 18" in e for e in validate_session(s2))
    s3 = demo_session()
    s3.edition = "narnia"
    assert "unknown edition" in validate_session(s3)[0]


# ---------------------------------------------------------------- analysis report


def test_analyze_report_contents() -> None:
    r = analyze(demo_session())
    assert r["ok"] and r["consistent"] and r["solution"]["exact"]
    # my cards and face-up knowledge are certain
    assert r["holders"]["Miss Scarlet"] == {"Me": 1.0}
    assert r["holders"]["Dagger"] == {"Bob": 1.0}
    # marginals are sane: each category's envelope probabilities sum to ~1
    cards = r["solution"]["cards"]
    for cat in (suspects("classic"), weapons("classic"), rooms("classic")):
        assert sum(cards.get(c, 0.0) for c in cat) == pytest.approx(1.0, abs=0.01)
    # guide is populated
    g = r["guide"]
    assert g["accusal"]["accuse"] is False and len(g["suggestions"]) == 3 and g["advice"]
    assert all(set(s) >= {"suspect", "weapon", "room", "score"} for s in g["suggestions"])
    assert r["threat"]["opponents"].keys() == {"Alice", "Bob", "Cara"}
    # none of my own cards can be in the envelope
    assert all(cards.get(c, 0.0) == 0.0 for c in MY_CARDS)


def test_analyze_solves_fully_specified_deal() -> None:
    # tell the analyst every card of every hand: exactly one solution must remain
    hands = {
        "Me": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
        "Alice": ["Col. Mustard", "Dagger", "Lounge", "Library", "Mrs. White"],
        "Bob": ["Lead Pipe", "Kitchen", "Ballroom", "Mr. Green"],
        "Cara": ["Revolver", "Conservatory", "Billiard Room", "Prof. Plum"],
    }  # envelope: Mrs. Peacock / Wrench / Dining Room
    s = AnalysisSession(players=list(hands), me="Me", my_cards=hands["Me"])
    for p, cs in hands.items():
        if p != "Me":
            s.observations.extend(FactObservation(player=p, card=c) for c in cs)
    r = analyze(s)
    assert r["ok"] and r["solution"]["n_possible"] == 1
    assert r["solution"]["best"] == ["Mrs. Peacock", "Wrench", "Dining Room"]
    assert r["guide"]["advice"][0].startswith("SOLVED")
    assert any(d.startswith("SOLVED") for d in r["deductions"])


def test_analyze_detects_contradictions() -> None:
    s = demo_session()
    s.observations.append(FactObservation(player="Alice", card="Prof. Plum", has=True))  # she passed on Plum earlier
    r = analyze(s)
    assert r["ok"] and not r["consistent"] and r["solution"]["n_possible"] == 0
    assert "contradictory" in r["guide"]["advice"][0]


def test_analyze_invalid_session_reports_errors() -> None:
    r = analyze(AnalysisSession(players=["A", "B"], me="A"))
    assert not r["ok"] and r["errors"]


def test_analyze_large_edition_sampled() -> None:
    s = AnalysisSession(
        edition="large",
        players=[f"P{i}" for i in range(1, 9)],
        me="P1",
        my_cards=["Miss Scarlet", "Poison", "Attic", "Wadsworth"],
        hand_sizes={f"P{i}": (5 if i == 1 else 4) for i in range(1, 9)},
    )
    s.hand_sizes = None
    s.observations.append(SuggestionObservation(suggester="P2", suspect="Yvette", weapon="Axe", room="Gazebo", disprover="P5"))
    r = analyze(s)
    assert r["ok"] and r["solution"]["exact"] is False and r["solution"]["n_possible"] >= 1
    assert r["hand_sizes"]["P1"] == 4  # 33 dealt cards over 8 players, pinned to my 4 cards


# ---------------------------------------------------------------- web route


def test_web_analyze_route() -> None:
    from fastapi.testclient import TestClient

    from clue.web.server import create_app
    from clue.web.settings import WebSettings

    client = TestClient(create_app(WebSettings()))
    r = client.post("/api/analyze", json=demo_session().model_dump())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["solution"]["n_possible"] > 0 and body["guide"]["advice"]
    r = client.post("/api/analyze", json={"players": ["A", "B"], "me": "A"})
    assert r.status_code == 200 and r.json()["ok"] is False
    assert client.post("/api/analyze", json={"observations": [{"type": "bogus"}]}).status_code == 422


# ---------------------------------------------------------------- Textual app

pytestmark_async = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_analyst_app_renders_and_edits(tmp_path: Path) -> None:
    app = AnalystApp(demo_session(), path=str(tmp_path / "sess.json"))
    async with app.run_test(size=(170, 50)) as pilot:
        await pilot.pause()
        assert app.report is not None and app.report["ok"]
        assert app.query_one("#probs", DataTable).row_count > 20
        # drive the suggestion flow through the UI
        app.action_add_suggestion()
        await pilot.pause()
        ol = app.query_one("#entry_choices", OptionList)
        for idx in (1, 0, 0, 0):  # Alice suggests Miss Scarlet / Candlestick / Hall
            ol.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
        assert app._step is not None
        ol.highlighted = app._step["resolved"].index("Me")  # I disproved
        await pilot.press("enter")
        await pilot.pause()
        ol.highlighted = 0  # showed Miss Scarlet
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.session.observations) == 5
        latest = app.session.observations[-1]
        assert observation_label(latest) == "Alice: Miss Scarlet / Candlestick / Hall -> Me showed Miss Scarlet"
        # fact flow via the Confirm button path
        app.action_add_fact()
        await pilot.pause()
        app.query_one("#entry_choices", OptionList).highlighted = 2  # Bob
        await pilot.click("#b_confirm")
        await pilot.pause()
        app.query_one("#entry_choices", OptionList).highlighted = 1  # does not hold
        await pilot.click("#b_confirm")
        await pilot.pause()
        app.query_one("#entry_choices", OptionList).highlighted = 3  # Mr. Green
        await pilot.click("#b_confirm")
        await pilot.pause()
        ob = app.session.observations[-1]
        assert isinstance(ob, FactObservation) and ob.player == "Bob" and not ob.has and ob.card == "Mr. Green"
        # undo + autosave + explicit save
        app.action_undo()
        await pilot.pause()
        assert len(app.session.observations) == 5
        app.action_save()
        saved = json.loads((tmp_path / "sess.json").read_text())
        assert len(saved["observations"]) == 5
        # escape cancels a flow
        app.action_add_fact()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app._flow_kind == ""


@pytest.mark.asyncio
async def test_analyst_app_setup_wizard_from_scratch() -> None:
    app = AnalystApp()
    async with app.run_test(size=(170, 50)) as pilot:
        await pilot.pause()
        assert app._flow_kind == "setup"  # wizard auto-starts with no session
        ol = app.query_one("#entry_choices", OptionList)
        ol.highlighted = 0  # classic
        await pilot.press("enter")
        await pilot.pause()
        inp = app.query_one("#entry_input", Input)
        inp.value = "North, East, South"
        await pilot.press("enter")
        await pilot.pause()
        ol.highlighted = 1  # me = East
        await pilot.press("enter")
        await pilot.pause()
        multi = app.query_one("#entry_multi", SelectionList)
        for v in ("Miss Scarlet", "Rope", "Hall", "Study", "Candlestick", "Wrench"):
            multi.select(v)
        await pilot.click("#b_confirm")
        await pilot.pause()
        await pilot.click("#b_confirm")  # no face-up cards
        await pilot.pause()
        assert app.session.players == ["North", "East", "South"] and app.session.me == "East"
        assert len(app.session.my_cards) == 6
        assert app.report is not None and app.report["ok"]
        assert app.report["hand_sizes"] == {"North": 6, "East": 6, "South": 6}


@pytest.mark.asyncio
async def test_analyst_app_flags_inconsistent_session() -> None:
    s = demo_session()
    s.observations.append(FactObservation(player="Alice", card="Prof. Plum", has=True))
    app = AnalystApp(s)
    async with app.run_test(size=(170, 50)) as pilot:
        await pilot.pause()
        assert app.report is not None and app.report["ok"] and not app.report["consistent"]
        app.action_undo()
        await pilot.pause()
        assert app.report["consistent"]


def test_cli_analyze_report(tmp_path: Path, capsys: Any) -> None:
    from clue.__main__ import _print_analysis

    report = analyze(demo_session())
    _print_analysis(report)
    out = capsys.readouterr().out
    assert "candidate solution(s)" in out and "Guide" in out and "Best suggestions" in out


# ---------------------------------------------------------------- card renames (display labels)


def test_card_names_validation() -> None:
    s = demo_session()
    s.card_names = {"Nope": "X", "Rope": " ", "Dagger": "Blade", "Lead Pipe": "blade", "Revolver": "Candlestick"}
    errs = "\n".join(validate_session(s))
    assert "'Nope' is not a classic-edition card" in errs
    assert "label for 'Rope' is empty" in errs
    assert "two cards share the label 'blade'" in errs
    assert "still the name of 'Candlestick'" in errs
    s.card_names = {"Mrs. White": "Dr. Orchid", "Lead Pipe": "Pipe"}
    assert validate_session(s) == []


def test_label_text_and_display_name() -> None:
    from clue.tools.analyst import display_name, label_text

    s = demo_session()
    s.card_names = {"Lead Pipe": "Pipe", "Mrs. Peacock": "Senora Azul", "Hall": "Grand Hall"}
    assert display_name(s, "Lead Pipe") == "Pipe" and display_name(s, "Rope") == "Rope"
    assert label_text(s, "Bob must hold Lead Pipe") == "Bob must hold Pipe"
    assert label_text(s, "SOLVED: Mrs. Peacock / Lead Pipe / Hall") == "SOLVED: Senora Azul / Pipe / Grand Hall"
    s.card_names = {}
    assert label_text(s, "Bob must hold Lead Pipe") == "Bob must hold Lead Pipe"


def test_analyze_report_uses_labels_in_display_strings() -> None:
    hands = {
        "Me": ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"],
        "Alice": ["Col. Mustard", "Dagger", "Lounge", "Library", "Mrs. White"],
        "Bob": ["Lead Pipe", "Kitchen", "Ballroom", "Mr. Green"],
        "Cara": ["Revolver", "Conservatory", "Billiard Room", "Prof. Plum"],
    }
    s = AnalysisSession(players=list(hands), me="Me", my_cards=hands["Me"], card_names={"Mrs. Peacock": "Senora Azul", "Wrench": "Llave", "Dining Room": "Comedor"})
    for p, cs in hands.items():
        if p != "Me":
            s.observations.extend(FactObservation(player=p, card=c) for c in cs)
    r = analyze(s)
    assert r["ok"] and r["card_names"]["Wrench"] == "Llave"
    # structured data stays canonical; display strings are labelled
    assert r["solution"]["best"] == ["Mrs. Peacock", "Wrench", "Dining Room"]
    assert r["guide"]["advice"][0] == "SOLVED - the envelope must be Senora Azul / Llave / Comedor. Accuse on your turn."
    assert any(d == "SOLVED: Senora Azul / Llave / Comedor" for d in r["deductions"])
    # conflict path is labelled too
    s2 = demo_session()
    s2.card_names = {"Prof. Plum": "Professor Pflaume"}
    s2.observations.append(FactObservation(player="Alice", card="Prof. Plum", has=True))
    r2 = analyze(s2)
    assert not r2["consistent"] and any("Professor Pflaume" in c for c in r2["conflicts"])


@pytest.mark.asyncio
async def test_analyst_app_rename_flow() -> None:
    app = AnalystApp(demo_session())
    async with app.run_test(size=(170, 50)) as pilot:
        await pilot.pause()
        app.action_rename()
        await pilot.pause()
        ol = app.query_one("#entry_choices", OptionList)
        assert app._step is not None
        ol.highlighted = app._step["resolved"].index("Lead Pipe")
        await pilot.press("enter")
        await pilot.pause()
        inp = app.query_one("#entry_input", Input)
        inp.value = "Bleirohr"
        await pilot.press("enter")
        await pilot.pause()
        assert app.session.card_names == {"Lead Pipe": "Bleirohr"}
        # the probability grid and card pickers now show the label
        rows = [str(app.query_one("#probs", DataTable).get_row_at(i)[0]) for i in range(app.query_one("#probs", DataTable).row_count)]
        assert any("Bleirohr" in r for r in rows) and not any("Lead Pipe" in r for r in rows)
        # renaming back to empty restores the canonical name
        app.action_rename()
        await pilot.pause()
        ol.highlighted = app._step["resolved"].index("Lead Pipe")
        await pilot.press("enter")
        await pilot.pause()
        app.query_one("#entry_input", Input).value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert app.session.card_names == {}


def test_cli_analyze_report_with_labels(capsys: Any) -> None:
    from clue.__main__ import _print_analysis

    s = demo_session()
    s.card_names = {"Lead Pipe": "Pipe-o-matic", "Ballroom": "Tanzsaal"}
    _print_analysis(analyze(s))
    out = capsys.readouterr().out
    assert "Pipe-o-matic" in out and "Tanzsaal" in out
    assert "Lead Pipe" not in out

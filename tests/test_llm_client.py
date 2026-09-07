"""Live-path hardening, tested offline with a monkeypatched httpx.post: backoff, cache, budget cap, native tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from clue.agents import llm_client as LC
from clue.agents.factory import make_agent, parse_players_arg
from clue.agents.llm_agent import LLMPlayerAgent
from clue.agents.llm_client import BudgetExceeded, CostTracker, MockLLMClient, OpenAICompatibleClient, ResponseCache
from clue.manager.game_manager import GameManager
from clue.manager.runner import run_game


class FakeHTTP:
    """Scripted responses: each item is (status, json_body)."""

    def __init__(self, script: list[tuple[int, dict[str, Any]]]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> httpx.Response:
        self.calls.append(json)
        status, body = self.script.pop(0)
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))


def _ok(text: str, pt: int = 100, ct: int = 20, tool_calls: list[dict[str, Any]] | None = None) -> tuple[int, dict[str, Any]]:
    msg: dict[str, Any] = {"role": "assistant", "content": text}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return 200, {"choices": [{"message": msg}], "usage": {"prompt_tokens": pt, "completion_tokens": ct}}


def test_backoff_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([(429, {"error": "slow down"}), (503, {}), _ok('{"a":1}')])
    monkeypatch.setattr(httpx, "post", fake)
    monkeypatch.setattr(LC.time, "sleep", lambda s: None)
    c = OpenAICompatibleClient("openai/gpt-4o-mini", "k", "https://x/v1", max_retries=3)
    r = c.complete("sys", [{"role": "user", "content": "hi"}])
    assert r.text == '{"a":1}' and len(fake.calls) == 3
    assert r.cost_usd == pytest.approx((100 * 0.15 + 20 * 0.60) / 1e6)


def test_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([(500, {})] * 3)
    monkeypatch.setattr(httpx, "post", fake)
    monkeypatch.setattr(LC.time, "sleep", lambda s: None)
    c = OpenAICompatibleClient("m", "k", "https://x/v1", max_retries=2)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        c.complete("sys", [{"role": "user", "content": "hi"}])


def test_budget_cap_blocks_next_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([_ok("x", pt=1_000_000, ct=0), _ok("y")])
    monkeypatch.setattr(httpx, "post", fake)
    tracker = CostTracker(max_usd=0.10)
    c = OpenAICompatibleClient("openai/gpt-4o-mini", "k", "https://x/v1", cost=tracker)
    c.complete("sys", [{"role": "user", "content": "1"}])  # costs $0.15 > cap
    with pytest.raises(BudgetExceeded):
        c.complete("sys", [{"role": "user", "content": "2"}])
    assert tracker.summary()["usd"] == pytest.approx(0.15)


def test_disk_cache_makes_rerun_free(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = FakeHTTP([_ok('{"a":1}')])
    monkeypatch.setattr(httpx, "post", fake)
    tracker = CostTracker()
    cache = ResponseCache(tmp_path / "cache")
    c = OpenAICompatibleClient("openai/gpt-4o-mini", "k", "https://x/v1", cost=tracker, cache=cache)
    r1 = c.complete("sys", [{"role": "user", "content": "same"}])
    r2 = c.complete("sys", [{"role": "user", "content": "same"}])
    assert not r1.cached and r2.cached and r2.text == r1.text
    assert len(fake.calls) == 1 and tracker.cached_calls == 1 and r2.cost_usd == 0.0


def test_json_mode_fallback_when_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([(400, {"error": "response_format not supported"}), _ok("{}")])
    monkeypatch.setattr(httpx, "post", fake)
    c = OpenAICompatibleClient("m", "k", "https://x/v1")
    c.complete("sys", [{"role": "user", "content": "hi"}], json_mode=True)
    assert "response_format" in fake.calls[0] and "response_format" not in fake.calls[1]
    assert c.supports_json_mode is False


def test_native_tool_loop_parses_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model asks for holder_probabilities via function calling, receives the result, then answers."""
    tc = [{"id": "c1", "type": "function", "function": {"name": "holder_probabilities", "arguments": "{}"}}]
    specs = parse_players_arg("llm:bayesian:native,baseline,baseline")
    gm = GameManager.create(specs, seed=3)
    obs = gm.get_observation("P1")
    obs["_notebook_obj"] = gm.notebooks["P1"]
    legal = gm.legal_actions("P1", include_accusations=False)
    hint = json.dumps({"reasoning": "ok", "action": legal[0].model_dump(exclude_none=True)})
    fake = FakeHTTP([_ok("", tool_calls=tc), _ok(hint)])
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAICompatibleClient("m", "k", "https://x/v1")
    agent = LLMPlayerAgent("P1", client=client, tool_mode="native")
    act = agent.choose_action(obs, legal)
    assert act == legal[0]
    assert agent.stats["native_tool_calls"] == 1
    # second request carried the tool result back to the model
    roles = [m["role"] for m in fake.calls[1]["messages"]]
    assert roles[-1] == "tool" and "tools" in fake.calls[0]


def test_native_mode_end_to_end_with_mock() -> None:
    specs = parse_players_arg("llm:bayesian:native:compact,baseline,baseline")
    assert specs[0].tool_mode == "native" and specs[0].prompt_profile == "compact" and specs[0].model is None
    gm = GameManager.create(specs, seed=4)
    agents = {s.id: make_agent(s, seed=4) for s in specs}
    run_game(gm, agents)
    a = agents["P1"]
    assert isinstance(a, LLMPlayerAgent) and isinstance(a.client, MockLLMClient)
    assert a.stats["native_tool_calls"] > 0 and a.stats["fallbacks"] == 0
    assert gm.summary()["illegal_attempts"].get("P1", 0) == 0

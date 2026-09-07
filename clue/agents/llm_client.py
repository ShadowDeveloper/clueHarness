"""Provider-agnostic chat client. Providers: openrouter, openai (any OpenAI-compatible URL incl.
Ollama/vLLM/LM Studio), anthropic, mock. Configured via env vars (.env) — no hard-coded keys.

Env:
  CLUE_LLM_PROVIDER = openrouter | openai | anthropic | local | mock   (default: mock)
  CLUE_LLM_MODEL    = default model id
  OPENROUTER_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
  OPENAI_BASE_URL   = e.g. http://localhost:11434/v1 for Ollama (provider=local)
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)
    cached: bool = False
    cost_usd: float = 0.0


class BudgetExceeded(RuntimeError):
    """Raised by CostTracker when the next call would push spend past the cap."""


class CostTracker:
    """Process-wide token / USD accounting with a hard cap. Prices are $/1M tokens (input, output)."""

    PRICES: dict[str, tuple[float, float]] = {
        "openrouter/free": (0.0, 0.0),
        "nvidia/nemotron-3-super-120b-a12b:free": (0.0, 0.0),
        "minimax/minimax-m3:free": (0.0, 0.0),
        "openai/gpt-4o-mini": (0.15, 0.60),
        "openai/gpt-4o": (2.50, 10.0),
        "openai/gpt-4.1-mini": (0.40, 1.60),
        "openai/gpt-4.1-nano": (0.10, 0.40),
        "anthropic/claude-3.5-haiku": (0.80, 4.0),
        "anthropic/claude-sonnet-4": (3.0, 15.0),
        "google/gemini-2.0-flash-001": (0.10, 0.40),
        "google/gemini-2.5-flash": (0.30, 2.50),
        "meta-llama/llama-3.1-8b-instruct": (0.02, 0.05),
        "deepseek/deepseek-chat-v3-0324": (0.27, 1.10),
    }

    def __init__(self, max_usd: float | None = None) -> None:
        self.max_usd = max_usd
        self.usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.cached_calls = 0
        self.lock = threading.Lock()

    def estimate(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pin, pout = self.PRICES.get(model, (1.0, 3.0))  # unknown model: conservative default
        return (prompt_tokens * pin + completion_tokens * pout) / 1e6

    def check(self) -> None:
        if self.max_usd is not None and self.usd >= self.max_usd:
            raise BudgetExceeded(f"spent ${self.usd:.4f} >= cap ${self.max_usd:.2f}")

    def add(self, model: str, usage: dict[str, Any], cached: bool, reported_cost: float | None = None) -> float:
        with self.lock:
            self.calls += 1
            if cached:
                self.cached_calls += 1
                return 0.0
            pt = int(usage.get("prompt_tokens", 0) or 0)
            ct = int(usage.get("completion_tokens", 0) or 0)
            self.prompt_tokens += pt
            self.completion_tokens += ct
            cost = float(reported_cost) if reported_cost is not None else self.estimate(model, pt, ct)
            self.usd += cost
            return cost

    def summary(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "usd": round(self.usd, 5),
            "max_usd": self.max_usd,
        }


class ResponseCache:
    """On-disk JSON cache keyed by sha256(model, system, messages, temperature, tools). Deterministic re-runs cost $0."""

    def __init__(self, path: str | Path | None) -> None:
        self.dir = Path(path) if path else None
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def key(self, *parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.dir:
            return None
        f = self.dir / f"{key}.json"
        if f.exists():
            try:
                data: dict[str, Any] = json.loads(f.read_text())
                return data
            except Exception:
                return None
        return None

    def put(self, key: str, data: dict[str, Any]) -> None:
        if self.dir:  # atomic: concurrent tournament threads/processes never observe a half-written entry
            tmp = self.dir / f"{key}.{os.getpid()}.{threading.get_ident()}.tmp"
            tmp.write_text(json.dumps(data))
            os.replace(tmp, self.dir / f"{key}.json")


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, messages: list[dict[str, Any]], temperature: float = 0.2, tools: list[dict[str, Any]] | None = None, json_mode: bool = False) -> LLMResponse: ...


def _load_dotenv() -> None:
    """Load `.env` from the CWD (python-dotenv if installed, else a minimal KEY=VALUE parser). Never overrides env."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        return
    except Exception:
        pass
    f = Path(".env")
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].strip().strip("'\"")
        os.environ.setdefault(k.strip(), v)


class OpenAICompatibleClient:
    """OpenAI chat-completions format; used for OpenRouter, OpenAI, Ollama, vLLM, LM Studio.

    Hardening: exponential backoff on 429/5xx/timeouts (`max_retries`), per-call timeout, optional JSON mode,
    native function calling (`tools=`), on-disk response cache, and cost accounting with a hard USD cap.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        max_retries: int = 4,
        cost: CostTracker | None = None,
        cache: ResponseCache | None = None,
        max_tokens: int = 1500,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self.timeout = timeout
        self.max_retries = max_retries
        self.cost = cost or CostTracker()
        self.cache = cache or ResponseCache(None)
        self.max_tokens = max_tokens
        self.supports_json_mode = True  # flipped off automatically if the provider rejects response_format
        self.supports_tools = True  # flipped off automatically if the provider rejects `tools`

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        delay = 1.0
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = httpx.post(f"{self.base_url}/chat/completions", headers=self.headers, json=body, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504, 524):
                    raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:200]}", request=r.request, response=r)
                if r.status_code == 400 and "response_format" in body and "response_format" in r.text:
                    self.supports_json_mode = False
                    body = {k: v for k, v in body.items() if k != "response_format"}
                    continue
                if r.status_code in (400, 404) and "tools" in body and ("tool" in r.text.lower() or "function" in r.text.lower()):
                    self.supports_tools = False  # provider/model without function calling: degrade to precomputed analysis
                    body = {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
                    continue
                r.raise_for_status()
                data: dict[str, Any] = r.json()
                if "error" in data and not data.get("choices"):
                    raise RuntimeError(f"provider error: {data['error']}")
                return data
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError, RuntimeError) as e:
                last = e
                if attempt == self.max_retries:
                    break
                time.sleep(delay + random.random() * 0.5)
                delay = min(delay * 2, 16.0)
        raise RuntimeError(f"LLM call failed after {self.max_retries + 1} attempts: {last}")

    def complete(self, system: str, messages: list[dict[str, Any]], temperature: float = 0.2, tools: list[dict[str, Any]] | None = None, json_mode: bool = False) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
            "usage": {"include": True},
        }
        if tools and self.supports_tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"
        elif json_mode and self.supports_json_mode:
            body["response_format"] = {"type": "json_object"}
        key = self.cache.key(self.model, system, messages, temperature, tools, json_mode)
        data = self.cache.get(key)
        cached = data is not None
        if data is None:
            self.cost.check()
            data = self._post(body)
            self.cache.put(key, data)
        msg = data["choices"][0]["message"]
        text = msg.get("content") or ""
        calls = [ToolCall(id=str(tc.get("id", f"call_{i}")), name=tc["function"]["name"], args=_parse_args(tc["function"].get("arguments"))) for i, tc in enumerate(msg.get("tool_calls") or [])]
        usage = data.get("usage", {}) or {}
        reported = usage.get("cost")
        cost = self.cost.add(self.model, usage, cached, float(reported) if reported is not None else None)
        return LLMResponse(text=text, raw=data, usage={k: v for k, v in usage.items() if isinstance(v, int)}, tool_calls=calls, cached=cached, cost_usd=cost)


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw or "{}")
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


class AnthropicClient:
    def __init__(self, model: str, api_key: str, timeout: float = 90.0) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, system: str, messages: list[dict[str, Any]], temperature: float = 0.2, tools: list[dict[str, Any]] | None = None, json_mode: bool = False) -> LLMResponse:
        body = {"model": self.model, "max_tokens": 1500, "temperature": temperature, "system": system, "messages": messages}
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return LLMResponse(text=text, raw=data, usage=data.get("usage", {}))


class MockLLMClient:
    """Offline stand-in. A `policy(system, messages) -> str` callable produces the text.

    Default policy: parse the observation JSON in the last user message and answer with the
    provided `hint` action (the heuristic recommendation embedded by the agent), so pipelines
    can be tested offline end-to-end. Set `fail_first=True` to return invalid JSON once, for
    testing the retry/fallback path.
    """

    model = "mock"

    def __init__(self, policy: Callable[[str, list[dict[str, str]]], str] | None = None, fail_first: bool = False, garbage_rate: float = 0.0, seed: int = 0) -> None:
        self.policy = policy
        self.fail_first = fail_first
        self.garbage_rate = garbage_rate
        self.calls = 0
        self.rng = random.Random(seed)

    def complete(self, system: str, messages: list[dict[str, Any]], temperature: float = 0.2, tools: list[dict[str, Any]] | None = None, json_mode: bool = False) -> LLMResponse:
        self.calls += 1
        if self.policy:
            return LLMResponse(text=self.policy(system, messages))
        if tools and not any(m.get("role") == "tool" for m in messages):
            # native-tool emulation: first call the solver tool, then answer once the result is in context
            return LLMResponse(text="", tool_calls=[ToolCall(id="call_mock", name="solution_probabilities", args={})])
        if (self.fail_first and self.calls == 1) or self.rng.random() < self.garbage_rate:
            return LLMResponse(text="I think I'll accuse Colonel Mustard with the banana in the garage!")
        last = str(next(m["content"] for m in messages if m["role"] == "user"))  # original observation
        if '"mode":"ponder"' in last:
            return LLMResponse(text=self._mock_ponder(messages))
        m = re.search(r"<recommended_action>(.*?)</recommended_action>", last, re.S)
        hint = json.loads(m.group(1).strip()) if m else {}
        if not hint:
            return LLMResponse(text=self._unguided(last))
        if "card" in hint:
            return LLMResponse(text=json.dumps({"reasoning": "mock: default disproof card", "card": hint["card"]}))
        return LLMResponse(text=json.dumps({"reasoning": "mock: following symbolic recommendation", "action": hint}))

    def _unguided(self, last: str) -> str:
        return _mock_unguided(self.rng, last)

    def _mock_ponder(self, messages: list[dict[str, str]]) -> str:
        """Round 1: ask for the posterior. Round 2: note the best guess and finish with a plan."""
        n_tool_results = sum(1 for m in messages if m["role"] == "user" and m["content"].startswith('{"tool_result"'))
        if n_tool_results == 0:
            return json.dumps({"thought": "mock: refresh posterior", "tool": "solution_probabilities", "args": {}})
        try:
            last = json.loads(messages[-1]["content"])["tool_result"]
            best = last.get("best")
            n = last.get("n_possible")
        except Exception:
            best, n = None, None
        notes = [f"{n} combos remain; leading guess {' / '.join(best)}"] if best else []
        return json.dumps({"thought": "mock: done", "plan": f"head for {best[2] if best else 'an unknown room'} and test {best[0] if best else 'an unseen suspect'}", "notes": notes, "done": True})


def _mock_unguided(rng: random.Random, last: str) -> str:
    """No-tools behaviour: pick a random legal action; accuse a random *unseen-by-hand* combo with small prob.

    This mimics an LLM reasoning without symbolic support: it respects the format but has no posterior.
    """
    try:
        obs = json.loads(last.split("\n<recommended_action>")[0])
    except Exception:
        return "{}"
    if "cards_that_can_disprove" in obs:
        return json.dumps({"reasoning": "mock unguided", "card": rng.choice(obs["cards_that_can_disprove"])})
    legal = [a for a in obs.get("legal_actions", []) if "<any" not in json.dumps(a)]
    suggest = [a for a in obs.get("legal_actions", []) if a.get("type") == "suggest"]
    cards = obs.get("cards", {})
    hand = set(obs.get("you", {}).get("hand", []))
    known = set(obs.get("notebook", {}).get("known_holder", {}))
    unseen = {k: [c for c in cards.get(k, []) if c not in hand and c not in known] for k in ("suspects", "weapons", "rooms")}
    # accuse when the unseen set is small (an LLM could notice this) or with small random prob
    n_combos = len(unseen["suspects"]) * len(unseen["weapons"]) * len(unseen["rooms"])
    if obs.get("can_accuse") and n_combos and (n_combos <= 2 or rng.random() < 0.03):
        return json.dumps(
            {
                "reasoning": "mock unguided accuse",
                "action": {"type": "accuse", "player": obs["you"]["id"], "suspect": rng.choice(unseen["suspects"]), "weapon": rng.choice(unseen["weapons"]), "room": rng.choice(unseen["rooms"])},
            }
        )
    if suggest:
        s = rng.choice(unseen["suspects"] or cards["suspects"])
        w = rng.choice(unseen["weapons"] or cards["weapons"])
        return json.dumps({"reasoning": "mock unguided suggest", "action": {"type": "suggest", "player": obs["you"]["id"], "suspect": s, "weapon": w, "room": suggest[0]["room"]}})
    rooms = [a for a in legal if a.get("type") == "move" and "," not in str(a.get("to"))]
    if rooms:
        return json.dumps({"reasoning": "mock unguided move to room", "action": rng.choice(rooms)})
    if not legal:
        return "{}"
    return json.dumps({"reasoning": "mock unguided", "action": rng.choice(legal)})


GLOBAL_COST = CostTracker()


def configure_budget(max_usd: float | None) -> CostTracker:
    """Set the process-wide hard spending cap (None = unlimited). Returns the shared tracker."""
    GLOBAL_COST.max_usd = max_usd
    return GLOBAL_COST


def make_client(provider: str | None = None, model: str | None = None, cache_dir: str | None = None) -> LLMClient:
    _load_dotenv()
    provider = (provider or os.getenv("CLUE_LLM_PROVIDER") or "mock").lower()
    model = model or os.getenv("CLUE_LLM_MODEL") or "mock"
    if provider == "mock" or model == "mock":
        return MockLLMClient()
    cache = ResponseCache(cache_dir or os.getenv("CLUE_LLM_CACHE") or None)
    kw: dict[str, Any] = {"cost": GLOBAL_COST, "cache": cache, "timeout": float(os.getenv("CLUE_LLM_TIMEOUT", "60"))}
    if provider == "openrouter":
        return OpenAICompatibleClient(
            model,
            os.environ["OPENROUTER_API_KEY"],
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            {"HTTP-Referer": "https://github.com/clue-harness", "X-Title": "clue-harness"},
            **kw,
        )
    if provider == "openai":
        return OpenAICompatibleClient(model, os.environ["OPENAI_API_KEY"], os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"), **kw)
    if provider == "local":
        return OpenAICompatibleClient(model, os.getenv("LOCAL_API_KEY", "ollama"), os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"), **kw)
    if provider == "anthropic":
        return AnthropicClient(model, os.environ["ANTHROPIC_API_KEY"])
    raise ValueError(f"unknown provider {provider!r}")


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply (tolerates ```json fences and prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                obj = json.loads(text[start : i + 1])
                if not isinstance(obj, dict):
                    raise ValueError("JSON is not an object")
                return obj
    raise ValueError("unbalanced JSON")

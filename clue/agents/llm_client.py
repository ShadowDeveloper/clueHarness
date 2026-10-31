"""Provider-agnostic LLM clients for OpenAI, OpenAI-compatible, and Anthropic APIs.

Supported wire formats are Chat Completions, legacy Completions, Responses, and Anthropic
Messages. ``provider`` selects credentials/defaults; ``api`` selects the wire format, so a
compatible gateway can use any model without a provider-specific client.

Configuration is loaded from ``.env`` on first construction. Explicit CLI/YAML settings are
passed with :class:`LLMConnection` and take precedence over environment variables. Secrets
are never included in cache keys or response logs.
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


@dataclass(frozen=True, repr=False)
class LLMConnection:
    """Run-specific API settings. ``None`` fields fall back to environment/provider defaults."""

    api: str | None = None
    api_key: str | None = None
    base_url: str | None = None

    def __repr__(self) -> str:
        key = "<set>" if self.api_key else None
        return f"LLMConnection(api={self.api!r}, api_key={key!r}, base_url={self.base_url!r})"


class BudgetExceeded(RuntimeError):
    """Raised by CostTracker when the next call would push spend past the cap."""


class CostTracker:
    """Process-wide token / USD accounting with a hard cap. Prices are $/1M tokens (input, output)."""

    PRICES: dict[str, tuple[float, float]] = {
        "openrouter/free": (0.0, 0.0),
        "nvidia/nemotron-3-super-120b-a12b:free": (0.0, 0.0),
        "minimax/minimax-m3:free": (0.0, 0.0),
        "openai/gpt-4o-mini": (0.15, 0.60),
        "gpt-4o-mini": (0.15, 0.60),
        "openai/gpt-4o": (2.50, 10.0),
        "gpt-4o": (2.50, 10.0),
        "openai/gpt-4.1-mini": (0.40, 1.60),
        "gpt-4.1-mini": (0.40, 1.60),
        "openai/gpt-4.1-nano": (0.10, 0.40),
        "gpt-4.1-nano": (0.10, 0.40),
        "anthropic/claude-3.5-haiku": (0.80, 4.0),
        "claude-3.5-haiku": (0.80, 4.0),
        "anthropic/claude-sonnet-4": (3.0, 15.0),
        "claude-sonnet-4": (3.0, 15.0),
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
    """On-disk JSON cache keyed by API, endpoint, and complete request body."""

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

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse: ...


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


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw or "{}")
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _content_text(content: Any) -> str:
    """Extract text from string or list-shaped content used by the supported APIs."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_content_text(part) for part in content)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
        if isinstance(text, dict):
            value = text.get("value")
            if isinstance(value, str):
                return value
        if content.get("type") in ("output_text", "input_text", "text"):
            value = content.get("value")
            return value if isinstance(value, str) else ""
    return ""


def _prompt_text(content: Any) -> str:
    text = _content_text(content)
    if text or content is None:
        return text
    if isinstance(content, (dict, list)):
        return json.dumps(content, separators=(",", ":"), default=str)
    return str(content)


def _normalise_usage(raw: Any, *, anthropic: bool = False) -> dict[str, int]:
    """Return common prompt/completion fields while retaining numeric provider usage details."""
    usage = raw if isinstance(raw, dict) else {}
    out = {str(k): v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
    pt = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    if anthropic:
        pt += int(usage.get("cache_creation_input_tokens", 0) or 0)
        pt += int(usage.get("cache_read_input_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    out["prompt_tokens"] = pt
    out["completion_tokens"] = ct
    out.setdefault("total_tokens", pt + ct)
    return out


def _reported_cost(data: dict[str, Any], usage: dict[str, Any]) -> float | None:
    for value in (usage.get("cost"), usage.get("cost_usd"), data.get("cost"), data.get("cost_usd")):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    return None


def _mentions(error: str, *fields: str) -> bool:
    low = error.lower()
    return any(field.lower() in low for field in fields)


class BaseHTTPClient:
    """Shared synchronous HTTP, retry, cache, usage, and cost implementation."""

    api = "unknown"

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str,
        *,
        auth: str = "bearer",
        extra_headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        max_retries: int = 4,
        cost: CostTracker | None = None,
        cache: ResponseCache | None = None,
        max_tokens: int = 1500,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if api_key:
            if auth == "anthropic":
                self.headers["x-api-key"] = api_key
            else:
                self.headers["Authorization"] = f"Bearer {api_key}"
        self.timeout = timeout
        self.max_retries = max_retries
        self.cost = cost or CostTracker()
        self.cache = cache or ResponseCache(None)
        self.max_tokens = max_tokens
        self.supports_json_mode = True
        self.supports_tools = True
        self.supports_temperature = True

    def _endpoint(self, path: str) -> str:
        # Accept either a versioned base URL or a full endpoint URL for custom gateways.
        return self.base_url if self.base_url.endswith(path) else f"{self.base_url}{path}"

    def _degrade(self, body: dict[str, Any], status: int, error: str) -> dict[str, Any] | None:
        """Remove a request option explicitly rejected by a model, once per client."""
        if status in (400, 404, 422) and "temperature" in body and _mentions(error, "temperature"):
            self.supports_temperature = False
            return {k: v for k, v in body.items() if k != "temperature"}
        return None

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        delay = 1.0
        retries = 0
        last: Exception | None = None
        current = body
        while True:
            try:
                r = httpx.post(self._endpoint(path), headers=self.headers, json=current, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504, 524):
                    raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:200]}", request=r.request, response=r)
                if r.status_code >= 400:
                    degraded = self._degrade(current, r.status_code, r.text)
                    if degraded is not None:
                        current = degraded
                        continue  # capability fallback is not a transient retry and works even with max_retries=0
                    raise RuntimeError(f"provider returned HTTP {r.status_code}: {r.text[:1000]}")
                data = r.json()
                if not isinstance(data, dict):
                    raise RuntimeError("provider returned a non-object JSON response")
                if data.get("error") and not any(k in data for k in ("choices", "output", "content")):
                    raise RuntimeError(f"provider error: {data['error']}")
                return data
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as e:
                last = e
                if retries >= self.max_retries:
                    break
                retries += 1
                time.sleep(delay + random.random() * 0.5)
                delay = min(delay * 2, 16.0)
        raise RuntimeError(f"LLM call failed after {self.max_retries + 1} attempts: {last}")

    def _request(
        self,
        path: str,
        body: dict[str, Any],
        parser: Callable[[dict[str, Any]], tuple[str, list[ToolCall]]],
        *,
        anthropic_usage: bool = False,
    ) -> LLMResponse:
        key = self.cache.key(self.api, self.base_url, body)
        data = self.cache.get(key)
        cached = data is not None
        if data is None:
            self.cost.check()
            data = self._post(path, body)
        text, calls = parser(data)
        if not cached:
            self.cache.put(key, data)
        raw_usage = data.get("usage", {}) or {}
        usage = _normalise_usage(raw_usage, anthropic=anthropic_usage)
        reported = _reported_cost(data, raw_usage if isinstance(raw_usage, dict) else {})
        cost = self.cost.add(self.model, usage, cached, reported)
        return LLMResponse(text=text, raw=data, usage=usage, tool_calls=calls, cached=cached, cost_usd=cost)


class OpenAICompatibleClient(BaseHTTPClient):
    """OpenAI Chat Completions, also used by OpenRouter and compatible local servers."""

    api = "chat_completions"

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
        super().__init__(
            model,
            api_key,
            base_url,
            extra_headers=extra_headers,
            timeout=timeout,
            max_retries=max_retries,
            cost=cost,
            cache=cache,
            max_tokens=max_tokens,
        )
        self.max_token_field = "max_tokens"
        self.system_role = "system"

    def _degrade(self, body: dict[str, Any], status: int, error: str) -> dict[str, Any] | None:
        if status in (400, 404, 422):
            messages = body.get("messages")
            if self.system_role in ("system", "developer") and isinstance(messages, list) and messages and messages[0].get("role") == self.system_role and _mentions(error, self.system_role):
                if self.system_role == "system":
                    self.system_role = "developer" if "developer" in error.lower() else "user"
                elif self.system_role == "developer":
                    self.system_role = "user"
                else:
                    return None
                out = dict(body)
                out["messages"] = [{"role": self.system_role, "content": messages[0].get("content", "")}, *messages[1:]]
                return out
            if "response_format" in body and _mentions(error, "response_format", "json mode", "json_object"):
                self.supports_json_mode = False
                return {k: v for k, v in body.items() if k != "response_format"}
            if "tools" in body and _mentions(error, "tool", "function"):
                self.supports_tools = False
                return {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
            if "max_tokens" in body and _mentions(error, "max_tokens"):
                # o-series and newer reasoning models use max_completion_tokens instead.
                self.max_token_field = "max_completion_tokens"
                out = {k: v for k, v in body.items() if k != "max_tokens"}
                out["max_completion_tokens"] = self.max_tokens
                return out
        return super()._degrade(body, status, error)

    def _parse(self, data: dict[str, Any]) -> tuple[str, list[ToolCall]]:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Chat Completions response has no choices: {data.get('error') or data}")
        msg = choices[0].get("message") or {}
        text = _content_text(msg.get("content"))
        if not text and isinstance(msg.get("refusal"), str):
            text = msg["refusal"]
        raw_calls = msg.get("tool_calls") or []
        calls = [
            ToolCall(
                id=str(tc.get("id", f"call_{i}")),
                name=str((tc.get("function") or {})["name"]),
                args=_parse_args((tc.get("function") or {}).get("arguments")),
            )
            for i, tc in enumerate(raw_calls)
        ]
        # Parse the deprecated single-function shape too; compatible gateways still sometimes emit it.
        if not calls and msg.get("function_call"):
            fc = msg["function_call"]
            calls.append(ToolCall(id="call_0", name=str(fc["name"]), args=_parse_args(fc.get("arguments"))))
        return text, calls

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            self.max_token_field: self.max_tokens,
            "messages": ([{"role": self.system_role, "content": system}] if system else []) + messages,
        }
        if self.supports_temperature:
            body["temperature"] = temperature
        if tools and self.supports_tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"
        elif json_mode and self.supports_json_mode:
            body["response_format"] = {"type": "json_object"}
        # Non-streaming Chat Completions returns usage by default. The stream-only
        # stream_options/include_usage fields are intentionally not sent.
        return self._request("/chat/completions", body, self._parse)


class OpenAICompletionsClient(BaseHTTPClient):
    """Legacy OpenAI ``/completions`` text-prompt API.

    This endpoint has no native tool or JSON-mode parameters. Tool results and conversation
    history are rendered into the prompt, and JSON mode adds an explicit output instruction.
    """

    api = "completions"

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
        super().__init__(
            model,
            api_key,
            base_url,
            extra_headers=extra_headers,
            timeout=timeout,
            max_retries=max_retries,
            cost=cost,
            cache=cache,
            max_tokens=max_tokens,
        )
        self.supports_tools = False
        self.supports_json_mode = False

    def _prompt(self, system: str, messages: list[dict[str, Any]], json_mode: bool, tools: list[dict[str, Any]] | None) -> str:
        parts = []
        if system:
            parts.append(f"System:\n{system}")
        for message in messages:
            role = str(message.get("role", "user")).upper()
            content = _prompt_text(message.get("content"))
            if message.get("tool_calls"):
                content += "\nTool calls: " + json.dumps(message["tool_calls"], separators=(",", ":"), default=str)
            if role == "TOOL":
                role = f"TOOL ({message.get('tool_call_id', 'unknown')})"
            parts.append(f"{role}:\n{content}")
        if tools:
            parts.append("System:\nThis legacy endpoint cannot emit native tool calls. Use the supplied analysis and answer directly.")
        if json_mode:
            parts.append("System:\nRespond with ONLY one valid JSON object. Do not use Markdown fences or add prose.")
        parts.append("ASSISTANT:\n")
        return "\n\n".join(parts)

    def _parse(self, data: dict[str, Any]) -> tuple[str, list[ToolCall]]:
        choices = data.get("choices") or []
        if not choices or "text" not in choices[0]:
            raise RuntimeError(f"Completions response has no text choice: {data.get('error') or data}")
        return str(choices[0].get("text") or ""), []

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": self._prompt(system, messages, json_mode, tools),
            "max_tokens": self.max_tokens,
        }
        if self.supports_temperature:
            body["temperature"] = temperature
        return self._request("/completions", body, self._parse)


# Explicit alias for readers who find "Completions" ambiguous with Chat Completions.
OpenAILegacyCompletionsClient = OpenAICompletionsClient


class OpenAIResponsesClient(BaseHTTPClient):
    """OpenAI Responses API, including stateless function-call and reasoning-item round trips."""

    api = "responses"

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
        super().__init__(
            model,
            api_key,
            base_url,
            extra_headers=extra_headers,
            timeout=timeout,
            max_retries=max_retries,
            cost=cost,
            cache=cache,
            max_tokens=max_tokens,
        )
        self.supports_reasoning_items = True
        self._output_by_call: dict[str, list[dict[str, Any]]] = {}

    def _degrade(self, body: dict[str, Any], status: int, error: str) -> dict[str, Any] | None:
        if status in (400, 404, 422):
            if "text" in body and _mentions(error, "text.format", "response_format", "json mode", "json_object"):
                self.supports_json_mode = False
                return {k: v for k, v in body.items() if k != "text"}
            if "tools" in body and _mentions(error, "tool", "function"):
                self.supports_tools = False
                return {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
            if "include" in body and _mentions(error, "include", "encrypted_content"):
                self.supports_reasoning_items = False
                return {k: v for k, v in body.items() if k != "include"}
        return super()._degrade(body, status, error)

    def _parse(self, data: dict[str, Any]) -> tuple[str, list[ToolCall]]:
        if data.get("status") == "failed" or (data.get("error") and not data.get("output")):
            raise RuntimeError(f"Responses API failed: {data.get('error') or data}")
        output = [item for item in (data.get("output") or []) if isinstance(item, dict)]
        texts: list[str] = []
        calls: list[ToolCall] = []
        for item in output:
            kind = item.get("type")
            if kind == "message":
                text = _content_text(item.get("content"))
                if text:
                    texts.append(text)
            elif kind in ("output_text", "text"):
                text = _content_text(item)
                if text:
                    texts.append(text)
            elif kind == "function_call":
                call_id = str(item.get("call_id") or item.get("id") or f"call_{len(calls)}")
                calls.append(ToolCall(id=call_id, name=str(item["name"]), args=_parse_args(item.get("arguments"))))
        if not texts and isinstance(data.get("output_text"), str):
            texts.append(data["output_text"])
        if calls:
            # Preserve reasoning items, encrypted content, message phase, and exact function-call
            # IDs for the next stateless request. The agent only needs the portable ToolCall shape.
            for call in calls:
                self._output_by_call[call.id] = output
        return "".join(texts), calls

    def _input(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            if role == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(message.get("tool_call_id", "")),
                        "output": _prompt_text(message.get("content")),
                    }
                )
                continue
            raw_calls = message.get("tool_calls") or []
            if role == "assistant" and raw_calls:
                original = next((self._output_by_call.get(str(tc.get("id", ""))) for tc in raw_calls if str(tc.get("id", "")) in self._output_by_call), None)
                if original is not None:
                    items.extend(original)
                    continue
                if _prompt_text(message.get("content")):
                    items.append({"role": "assistant", "content": _prompt_text(message.get("content"))})
                for i, tc in enumerate(raw_calls):
                    function = tc.get("function") or {}
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": str(tc.get("id", f"call_{i}")),
                            "name": str(function.get("name", "")),
                            "arguments": function.get("arguments") if isinstance(function.get("arguments"), str) else json.dumps(function.get("arguments") or {}),
                        }
                    )
                continue
            content = _prompt_text(message.get("content"))
            if content or role in ("user", "assistant"):
                items.append({"role": role if role in ("user", "assistant", "system", "developer") else "user", "content": content})
        return items

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": system,
            "input": self._input(messages),
            "max_output_tokens": self.max_tokens,
        }
        if self.supports_temperature:
            body["temperature"] = temperature
        if self.supports_reasoning_items:
            body["include"] = ["reasoning.encrypted_content"]
        if tools and self.supports_tools:
            body["tools"] = [
                {
                    "type": "function",
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                    "strict": t.get("strict", False),
                }
                for t in tools
            ]
            body["tool_choice"] = "auto"
        elif json_mode and self.supports_json_mode:
            body["text"] = {"format": {"type": "json_object"}}
        return self._request("/responses", body, self._parse)


# Short alias matching the API name.
ResponsesClient = OpenAIResponsesClient


class AnthropicClient(BaseHTTPClient):
    """Anthropic Messages API with native tool use and structured-output fallback."""

    api = "messages"

    def __init__(
        self,
        model: str,
        api_key: str,
        timeout: float = 90.0,
        max_retries: int = 4,
        cost: CostTracker | None = None,
        cache: ResponseCache | None = None,
        max_tokens: int = 1500,
        base_url: str = "https://api.anthropic.com/v1",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            model,
            api_key,
            base_url,
            auth="anthropic",
            extra_headers={"anthropic-version": "2023-06-01", **(extra_headers or {})},
            timeout=timeout,
            max_retries=max_retries,
            cost=cost,
            cache=cache,
            max_tokens=max_tokens,
        )
        self._content_by_tool: dict[str, list[dict[str, Any]]] = {}

    def _degrade(self, body: dict[str, Any], status: int, error: str) -> dict[str, Any] | None:
        if status in (400, 404, 422):
            if "output_config" in body and _mentions(error, "output_config", "output format", "json_schema", "structured"):
                self.supports_json_mode = False
                return {k: v for k, v in body.items() if k != "output_config"}
            if "tools" in body and _mentions(error, "tool", "function"):
                self.supports_tools = False
                return {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
        return super()._degrade(body, status, error)

    def _parse(self, data: dict[str, Any]) -> tuple[str, list[ToolCall]]:
        content = [block for block in (data.get("content") or []) if isinstance(block, dict)]
        texts = [_content_text(block) for block in content if block.get("type") == "text"]
        calls = [ToolCall(id=str(block.get("id", f"call_{i}")), name=str(block["name"]), args=_parse_args(block.get("input"))) for i, block in enumerate(content) if block.get("type") == "tool_use"]
        if calls:
            # Extended-thinking blocks (including signatures) must accompany tool_use blocks
            # when the conversation is sent back to Messages.
            for call in calls:
                self._content_by_tool[call.id] = content
        if not content and data.get("type") == "error":
            raise RuntimeError(f"Messages API failed: {data.get('error') or data}")
        return "".join(texts), calls

    @staticmethod
    def _append(messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": blocks})

    def _messages(self, messages: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
        system: list[str] = []
        out: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            if role in ("system", "developer"):
                system.append(_prompt_text(message.get("content")))
            elif role == "tool":
                self._append(
                    out,
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": str(message.get("tool_call_id", "")),
                            "content": _prompt_text(message.get("content")),
                        }
                    ],
                )
            elif role == "assistant":
                raw_calls = message.get("tool_calls") or []
                original = next((self._content_by_tool.get(str(tc.get("id", ""))) for tc in raw_calls if str(tc.get("id", "")) in self._content_by_tool), None)
                if original is not None:
                    self._append(out, "assistant", original)
                    continue
                blocks: list[dict[str, Any]] = []
                text = _prompt_text(message.get("content"))
                if text:
                    blocks.append({"type": "text", "text": text})
                for i, tc in enumerate(raw_calls):
                    function = tc.get("function") or {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": str(tc.get("id", f"call_{i}")),
                            "name": str(function.get("name", "")),
                            "input": _parse_args(function.get("arguments")),
                        }
                    )
                self._append(out, "assistant", blocks)
            else:
                text = _prompt_text(message.get("content"))
                self._append(out, "user", [{"type": "text", "text": text}])
        return system, out

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        extra_system, converted = self._messages(messages)
        system_parts = ([system] if system else []) + extra_system
        if json_mode:
            system_parts.append("Respond with ONLY one valid JSON object, without Markdown fences or surrounding prose.")
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": "\n\n".join(part for part in system_parts if part),
            "messages": converted,
        }
        if self.supports_temperature:
            body["temperature"] = temperature
        if tools and self.supports_tools:
            body["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]
            body["tool_choice"] = {"type": "auto"}
        elif json_mode and self.supports_json_mode:
            # Messages currently exposes Structured Outputs through output_config. Older
            # models reject it; _degrade then retains the prompt-only JSON behaviour.
            body["output_config"] = {"format": {"type": "json_schema", "schema": {"type": "object"}}}
        return self._request("/messages", body, self._parse, anthropic_usage=True)


MessagesClient = AnthropicClient


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

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
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


_API_ALIASES = {
    "chat": "chat_completions",
    "chat-completions": "chat_completions",
    "chat_completions": "chat_completions",
    "openai-chat": "chat_completions",
    "completion": "completions",
    "completions": "completions",
    "legacy": "completions",
    "legacy-completions": "completions",
    "legacy_completions": "completions",
    "responses": "responses",
    "openai-responses": "responses",
    "messages": "messages",
    "anthropic": "messages",
    "anthropic-messages": "messages",
}

_PROVIDER_APIS = {
    "responses": ("openai", "responses"),
    "chat": ("openai", "chat_completions"),
    "chat-completions": ("openai", "chat_completions"),
    "chat_completions": ("openai", "chat_completions"),
    "completions": ("openai", "completions"),
    "legacy-completions": ("openai", "completions"),
    "messages": ("anthropic", "messages"),
}


def _canonical_api(api: str) -> str:
    key = api.strip().lower()
    if key not in _API_ALIASES:
        raise ValueError(f"unknown LLM API {api!r}; choose chat_completions | completions | responses | messages")
    return _API_ALIASES[key]


def make_client(
    provider: str | None = None,
    model: str | None = None,
    cache_dir: str | None = None,
    *,
    api: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    connection: LLMConnection | None = None,
) -> LLMClient:
    """Build a client using explicit settings > YAML/CLI connection > env > provider defaults."""
    _load_dotenv()
    conn = connection or LLMConnection()
    api = api or conn.api or os.getenv("CLUE_LLM_API")
    api_key = api_key or conn.api_key
    base_url = base_url or conn.base_url
    configured_provider = provider or os.getenv("CLUE_LLM_PROVIDER")
    provider = (configured_provider or "mock").strip().lower()
    if provider in _PROVIDER_APIS:
        provider, provider_api = _PROVIDER_APIS[provider]
        api = api or provider_api
    model = model or os.getenv("CLUE_LLM_MODEL") or "mock"
    if model == "mock" or provider == "mock" and (configured_provider is not None or not api):
        return MockLLMClient()
    if provider == "mock":
        if not api:  # explicit provider/model selection is required to leave offline mode
            return MockLLMClient()
        provider = "anthropic" if _canonical_api(api) == "messages" else "openai"
    wire_api = _canonical_api(api or ("messages" if provider == "anthropic" else "chat_completions"))

    cache = ResponseCache(cache_dir or os.getenv("CLUE_LLM_CACHE") or None)
    key = api_key or os.getenv("CLUE_LLM_API_KEY")
    if not key:
        if provider == "openrouter":
            key = os.getenv("OPENROUTER_API_KEY")
        elif provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
        elif provider == "local":
            key = os.getenv("LOCAL_API_KEY")
        elif provider == "anthropic":
            key = os.getenv("ANTHROPIC_API_KEY")
    if provider == "local" and key is None:
        key = "ollama"  # accepted by Ollama; compatible servers may simply ignore it

    url = base_url or os.getenv("CLUE_LLM_BASE_URL")
    if not url:
        if provider == "openrouter":
            url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        elif provider == "openai":
            url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        elif provider == "local":
            url = os.getenv("LOCAL_BASE_URL") or os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
        elif provider == "anthropic":
            url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        else:
            raise ValueError(f"unknown provider {provider!r}")
    if not url:
        raise ValueError("missing LLM base URL")
    if provider not in ("openrouter", "openai", "local", "anthropic"):
        raise ValueError(f"unknown provider {provider!r}")
    if provider != "local" and not key:
        key_name = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}[provider]
        raise ValueError(f"missing API key: use --api-key/YAML llm.api_key, CLUE_LLM_API_KEY, or {key_name}")

    headers: dict[str, str] = {}
    if provider == "openrouter":
        headers = {"HTTP-Referer": "https://github.com/clue-harness", "X-Title": "clue-harness"}
    elif provider == "openai":
        if org := os.getenv("OPENAI_ORG_ID"):
            headers["OpenAI-Organization"] = org
        if project := os.getenv("OPENAI_PROJECT_ID"):
            headers["OpenAI-Project"] = project
    kw: dict[str, Any] = {
        "cost": GLOBAL_COST,
        "cache": cache,
        "timeout": float(os.getenv("CLUE_LLM_TIMEOUT", "60")),
        "max_retries": int(os.getenv("CLUE_LLM_MAX_RETRIES", "4")),
        "max_tokens": int(os.getenv("CLUE_LLM_MAX_TOKENS", "1500")),
    }
    if wire_api == "messages":
        return AnthropicClient(model, key or "", base_url=url, extra_headers=headers, **kw)
    if wire_api == "responses":
        return OpenAIResponsesClient(model, key, url, headers, **kw)
    if wire_api == "completions":
        return OpenAICompletionsClient(model, key, url, headers, **kw)
    return OpenAICompatibleClient(model, key, url, headers, **kw)


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

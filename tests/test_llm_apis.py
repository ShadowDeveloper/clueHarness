"""Offline wire-format and authentication coverage for all supported live LLM APIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

import clue.__main__ as cli
from clue.agents.llm_client import (
    AnthropicClient,
    LLMConnection,
    MockLLMClient,
    OpenAICompatibleClient,
    OpenAICompletionsClient,
    OpenAIResponsesClient,
    make_client,
)


class FakeHTTP:
    def __init__(self, script: list[tuple[int, dict[str, Any]]]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.urls: list[str] = []
        self.headers: list[dict[str, str]] = []

    def __call__(self, url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> httpx.Response:
        self.urls.append(url)
        self.headers.append(headers)
        self.calls.append(json)
        status, body = self.script.pop(0)
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))


def _chat(text: str = "{}") -> tuple[int, dict[str, Any]]:
    return 200, {"choices": [{"message": {"role": "assistant", "content": text}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}


def _response_text(text: str = "{}") -> tuple[int, dict[str, Any]]:
    return 200, {
        "status": "completed",
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14},
    }


def _message_text(text: str = "{}") -> tuple[int, dict[str, Any]]:
    return 200, {"type": "message", "role": "assistant", "content": [{"type": "text", "text": text}], "usage": {"input_tokens": 8, "output_tokens": 2}}


def _tool_spec() -> dict[str, Any]:
    return {
        "name": "solution_probabilities",
        "description": "Return solution probabilities",
        "parameters": {"type": "object", "properties": {"threshold": {"type": "number"}}},
    }


def _append_tool_round(messages: list[dict[str, Any]], response: Any, result: dict[str, Any]) -> None:
    call = response.tool_calls[0]
    messages.append(
        {
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.args)}}],
        }
    )
    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})


def test_chat_completions_auth_and_reasoning_model_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP(
        [
            (400, {"error": {"message": "max_tokens is unsupported; use max_completion_tokens"}}),
            (400, {"error": {"message": "temperature is not supported by this reasoning model"}}),
            _chat('{"ok":true}'),
            _chat('{"ok":true}'),
        ]
    )
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAICompatibleClient("reasoning-model", "secret", "https://gateway/v1", max_retries=0)

    response = client.complete("system", [{"role": "user", "content": "hello"}], json_mode=True)

    assert response.text == '{"ok":true}'
    # The token-parameter and temperature capabilities are remembered on later calls.
    client.complete("system", [{"role": "user", "content": "hello again"}], json_mode=True)
    assert fake.urls == ["https://gateway/v1/chat/completions"] * 4
    assert fake.headers[0]["Authorization"] == "Bearer secret"
    final = fake.calls[2]
    assert final["max_completion_tokens"] == 1500
    assert "max_tokens" not in final and "temperature" not in final and "usage" not in final
    assert final["response_format"] == {"type": "json_object"}
    assert fake.calls[3]["max_completion_tokens"] == 1500 and "max_tokens" not in fake.calls[3]


def test_chat_completions_system_role_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP(
        [
            (400, {"error": {"message": "messages[0].role: system is unsupported; use developer"}}),
            (400, {"error": {"message": "messages[0].role: developer is unsupported"}}),
            _chat(),
            _chat(),
        ]
    )
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAICompatibleClient("m", "k", "https://x/v1", max_retries=0)

    client.complete("instructions", [{"role": "user", "content": "one"}])
    client.complete("instructions", [{"role": "user", "content": "two"}])

    assert [call["messages"][0]["role"] for call in fake.calls] == ["system", "developer", "user", "user"]


def test_legacy_completions_prompt_and_response_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([(200, {"choices": [{"text": '{"legacy":true}'}], "usage": {"prompt_tokens": 4, "completion_tokens": 1}})])
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAICompletionsClient("gpt-3.5-turbo-instruct", "legacy-key", "https://gateway/v1")
    messages = [{"role": "user", "content": "observation"}, {"role": "tool", "tool_call_id": "call-1", "content": '{"answer":42}'}]

    response = client.complete("system rules", messages, tools=[_tool_spec()], json_mode=True)

    assert response.text == '{"legacy":true}' and response.tool_calls == []
    assert response.usage["prompt_tokens"] == 4 and response.usage["completion_tokens"] == 1
    body = fake.calls[0]
    assert fake.urls[0] == "https://gateway/v1/completions"
    assert fake.headers[0]["Authorization"] == "Bearer legacy-key"
    assert "messages" not in body and "tools" not in body and "response_format" not in body
    assert "System:\nsystem rules" in body["prompt"]
    assert "TOOL (call-1)" in body["prompt"] and "ONLY one valid JSON object" in body["prompt"]


def test_responses_native_tools_reasoning_round_trip_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    first = (
        200,
        {
            "status": "completed",
            "output": [
                {"type": "reasoning", "id": "rs_1", "encrypted_content": "encrypted"},
                {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "solution_probabilities", "arguments": '{"threshold":0.9}'},
            ],
            "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        },
    )
    fake = FakeHTTP([first, _response_text('{"action":{}}')])
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAIResponsesClient("gpt-4o-mini", "responses-key", "https://gateway/v1")
    messages: list[dict[str, Any]] = [{"role": "user", "content": "observation"}]

    initial = client.complete("instructions", messages, tools=[_tool_spec()])
    assert initial.tool_calls[0].id == "call_1" and initial.tool_calls[0].args == {"threshold": 0.9}
    assert initial.usage["prompt_tokens"] == 20 and initial.usage["completion_tokens"] == 5
    _append_tool_round(messages, initial, {"best": ["Scarlet", "Rope", "Hall"]})
    final = client.complete("instructions", messages, json_mode=True)

    assert final.text == '{"action":{}}'
    first_body, second_body = fake.calls
    assert fake.urls == ["https://gateway/v1/responses", "https://gateway/v1/responses"]
    assert fake.headers[0]["Authorization"] == "Bearer responses-key"
    assert first_body["instructions"] == "instructions" and first_body["max_output_tokens"] == 1500
    assert first_body["include"] == ["reasoning.encrypted_content"]
    assert first_body["tools"] == [
        {
            "type": "function",
            "name": "solution_probabilities",
            "description": "Return solution probabilities",
            "parameters": _tool_spec()["parameters"],
            "strict": False,
        }
    ]
    assert second_body["text"] == {"format": {"type": "json_object"}}
    assert [item.get("type", "message") for item in second_body["input"]] == ["message", "reasoning", "function_call", "function_call_output"]
    assert second_body["input"][1]["encrypted_content"] == "encrypted"
    assert second_body["input"][2]["id"] == "fc_1" and second_body["input"][2]["call_id"] == "call_1"
    assert second_body["input"][3] == {"type": "function_call_output", "call_id": "call_1", "output": '{"best": ["Scarlet", "Rope", "Hall"]}'}


def test_responses_capability_fallbacks_do_not_consume_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP(
        [
            (400, {"error": {"message": "include reasoning.encrypted_content is unsupported"}}),
            (400, {"error": {"message": "temperature is not supported"}}),
            _response_text(),
        ]
    )
    monkeypatch.setattr(httpx, "post", fake)
    client = OpenAIResponsesClient("m", "k", "https://x/v1", max_retries=0)

    client.complete("sys", [{"role": "user", "content": "hi"}])

    assert len(fake.calls) == 3
    assert "include" not in fake.calls[-1] and "temperature" not in fake.calls[-1]


def test_anthropic_native_tools_thinking_round_trip_and_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    first = (
        200,
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "private reasoning", "signature": "signed"},
                {"type": "tool_use", "id": "toolu_1", "name": "solution_probabilities", "input": {"threshold": 0.9}},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 2, "cache_read_input_tokens": 3},
        },
    )
    fake = FakeHTTP([first, _message_text('{"action":{}}')])
    monkeypatch.setattr(httpx, "post", fake)
    client = AnthropicClient("claude-sonnet-4", "anthropic-key", base_url="https://anthropic-gateway/v1")
    messages: list[dict[str, Any]] = [{"role": "user", "content": "observation"}]

    initial = client.complete("system", messages, tools=[_tool_spec()])
    assert initial.tool_calls[0].id == "toolu_1" and initial.tool_calls[0].args == {"threshold": 0.9}
    assert initial.usage["prompt_tokens"] == 15 and initial.usage["completion_tokens"] == 5
    _append_tool_round(messages, initial, {"n_possible": 1})
    final = client.complete("system", messages, json_mode=True)

    assert final.text == '{"action":{}}'
    first_body, second_body = fake.calls
    assert fake.urls == ["https://anthropic-gateway/v1/messages"] * 2
    assert fake.headers[0]["x-api-key"] == "anthropic-key"
    assert fake.headers[0]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in fake.headers[0]
    assert first_body["tools"][0]["input_schema"] == _tool_spec()["parameters"]
    assert first_body["tool_choice"] == {"type": "auto"}
    assert second_body["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert second_body["messages"][1]["content"][0]["signature"] == "signed"
    assert second_body["messages"][1]["content"][1]["type"] == "tool_use"
    assert second_body["messages"][2]["content"] == [{"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"n_possible": 1}'}]
    assert "ONLY one valid JSON object" in second_body["system"]


def test_anthropic_structured_output_fallback_and_remembered_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP([(400, {"type": "error", "error": {"message": "output_config is not supported"}}), _message_text("one"), _message_text("two")])
    monkeypatch.setattr(httpx, "post", fake)
    client = AnthropicClient("claude-old", "k", max_retries=0)

    assert client.complete("sys", [{"role": "user", "content": "one"}], json_mode=True).text == "one"
    assert client.complete("sys", [{"role": "user", "content": "two"}], json_mode=True).text == "two"

    assert len(fake.calls) == 3
    assert "output_config" not in fake.calls[1] and "output_config" not in fake.calls[2]
    assert client.supports_json_mode is False


@pytest.mark.parametrize(
    ("provider", "api", "client_type", "auth_header"),
    [
        ("openai", "chat_completions", OpenAICompatibleClient, "Authorization"),
        ("openai", "completions", OpenAICompletionsClient, "Authorization"),
        ("openai", "responses", OpenAIResponsesClient, "Authorization"),
        ("anthropic", "messages", AnthropicClient, "x-api-key"),
    ],
)
def test_factory_generic_key_auth_for_every_api(provider: str, api: str, client_type: type, auth_header: str) -> None:
    connection = LLMConnection(api=api, api_key="run-secret", base_url="https://gateway/v1")

    client = make_client(provider, "any-model", connection=connection)

    assert isinstance(client, client_type)
    assert client.base_url == "https://gateway/v1"
    assert client.headers[auth_header] == ("run-secret" if auth_header == "x-api-key" else "Bearer run-secret")
    assert "run-secret" not in repr(connection) and "<set>" in repr(connection)


def test_factory_generic_environment_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUE_LLM_API", "responses")
    monkeypatch.setenv("CLUE_LLM_API_KEY", "env-secret")
    monkeypatch.setenv("CLUE_LLM_BASE_URL", "https://env-gateway/v1")

    client = make_client("openai", "any-model")

    assert isinstance(client, OpenAIResponsesClient)
    assert client.base_url == "https://env-gateway/v1"
    assert client.headers["Authorization"] == "Bearer env-secret"


def test_factory_requires_key_except_for_local(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CLUE_LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="missing API key"):
        make_client("openai", "model", api="responses")

    local = make_client("local", "model", api="chat_completions", api_key=None, base_url="http://local/v1")
    assert isinstance(local, OpenAICompatibleClient)
    assert isinstance(make_client("mock", "model", api="responses", api_key="unused"), MockLLMClient)


def test_cli_and_yaml_connection_precedence_and_secret_redaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "game.yaml"
    config.write_text(
        """llm:
  provider: mock
  model: mock
  api: completions
  api_key: yaml-secret
  base_url: https://yaml/v1
players:
  - {kind: llm}
  - {kind: baseline}
  - {kind: baseline}
"""
    )
    replay_dir = tmp_path / "replays"
    seen: dict[str, Any] = {}
    original_make_agent = cli.make_agent

    def capture(spec: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)
        return original_make_agent(spec, **kwargs)

    monkeypatch.setattr(cli, "make_agent", capture)
    monkeypatch.setattr(cli, "run_game", lambda *args, **kwargs: None)
    result = CliRunner().invoke(
        cli.app,
        [
            "play",
            "--config",
            str(config),
            "--ui",
            "cli",
            "--quiet",
            "--api",
            "responses",
            "--api-key",
            "cli-secret",
            "--base-url",
            "https://cli/v1",
            "--replay-dir",
            str(replay_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    connection = seen["connection"]
    assert isinstance(connection, LLMConnection)
    assert connection.api == "responses" and connection.api_key == "cli-secret" and connection.base_url == "https://cli/v1"
    replay = next(replay_dir.glob("*.jsonl")).read_text()
    assert "cli-secret" not in replay and "yaml-secret" not in replay

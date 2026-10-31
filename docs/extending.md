# Extending the harness

## Add an LLM provider
Most providers need no new class. Choose one of the four wire implementations in
`clue/agents/llm_client.py` and supply a model, versioned base URL, and key:

| `api` | Client | Native tools / JSON |
|---|---|---|
| `chat_completions` | `OpenAICompatibleClient` | Chat tools / `response_format` |
| `completions` | `OpenAICompletionsClient` | No native channel; prompt-rendered history and JSON instruction |
| `responses` | `OpenAIResponsesClient` | Flattened function tools / `text.format`; reasoning-item round trips |
| `messages` | `AnthropicClient` | `tool_use` / `output_config.format`; thinking-block round trips |

Use `--provider openai|local|anthropic --api ... --base-url ... --api-key ...`, YAML `llm:`, or the
corresponding environment variables. `CLUE_LLM_API_KEY` works with every API; OpenAI-wire clients send a
Bearer token and Messages sends `x-api-key`. Provider-specific key variables remain supported.

For a genuinely different protocol, implement the same interface:
```python
class MyClient:
    model: str
    def complete(
        self, system: str, messages: list[dict[str, Any]], temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None, json_mode: bool = False,
    ) -> LLMResponse:
        ...  # normalized text, tool calls, prompt_tokens/completion_tokens, and cost
```
Register it in `make_client`. Subclassing `BaseHTTPClient` supplies retries, caching, authentication,
usage normalization, and budget accounting.

### Native function calling (optional)
`LLMPlayerAgent` pre-computes tools into the prompt as a baseline. In `native` mode it passes `TOOL_SPECS`
to the client, dispatches each returned `ToolCall` through `_tool` (which logs it), and appends portable
assistant/tool messages. Each wire client translates those messages to its API's required tool-call and
tool-result items. Legacy Completions cannot emit native calls and therefore answers directly.

## Add an agent
```python
from clue.agents.base import PlayerAgent
from clue.rules import Action

class MyBot(PlayerAgent):
    kind = "baseline"
    def choose_action(self, observation, legal_actions) -> Action:
        # legal_actions excludes accusations; observation["can_accuse"] tells you if accusing is allowed
        ...
    def choose_card_to_show(self, observation, cards_that_can_disprove) -> str:
        ...
```
Optionally set `supports_ponder = True` and implement `ponder(observation, ctx)` to think between turns
(see `pondering.md`). Register in `clue/agents/factory.py::make_agent` (e.g. `bot: mybot`). Use `observation["_notebook_obj"]`
for the live `Notebook` when calling `clue.tools` functions. Returning an illegal action is safe — the runner
rejects it, retries once with `observation["last_error"]`, then substitutes a legal fallback and logs both.

## Add a UI / transport
The TUI and shipped FastAPI/React web UI are adapters over `GameManager.get_observation(pid)`,
`legal_actions(pid)`, `step(action)`, and `export_replay(viewer)`. The web implementation lives in `clue/web/`
and `web/`; its `WebHumanAgent` uses the same request/queue pattern as `TUIHumanAgent`. Use
[`web.md`](web.md) for current routes and frontend development instructions.

## Add a rule variant
1. Add a field to `GameConfig` (`clue/rules/state.py`) with the official behaviour as default.
2. Branch on it inside `engine.py` / `board.py` only.
3. Document it in `RULES_SPEC.md` and add a test to `tests/test_rules.py`.
Existing examples: `dice`, `deal_remainder`, `edition`.

## Add a metric
`clue/eval/tournament.py::run_tournament` aggregates `GameManager.summary()`. Add the raw number to
`summary()` (manager), accumulate it in the `per` dict, and emit it in the `table` rows; `write_csv` and
`markdown_table` pick columns up automatically. Chart it in `clue/eval/report.py::_charts`.

## Add a card set (e.g. a themed edition)
`clue/rules/cards.py` holds the tuples. Rooms are tied to the board footprint (`board.py: ROOM_RECTS,
DOORS`), so renaming rooms means updating both; suspects/weapons are free-standing.

## Development workflow
```
pip install -e ".[dev]"
pytest -q                     # full Python test suite (includes headless TUI, solver, expert bot, glue/CLI); use --workers in tournaments for parallel games
pytest -q tests/test_rules.py # engine only (~2 s)
ruff format . && ruff check . && mypy clue
python eval/make_demo.py            # regenerate demo_game.md
python eval/make_tui_screenshot.py  # regenerate docs/tui_screenshot.*
python -m clue eval --games 50      # regenerate eval/report.md + charts.png
```
Invariants to preserve: `clue.rules` imports nothing outside itself; the manager contains no strategy text;
every action applied goes through `rules.is_legal`; event-level sensitive payloads stay in `Event.private` with
an explicit `private_to` (private action/log records use the corresponding `LogRecord` fields).

## Web UI

Backend routes live in `clue/web/routes/*.py`; every outbound game payload goes through `GameSession.render_*`
(keep it that way - the privacy test in `tests/test_web.py` checks frames, not routes). New frontend pages go in
`web/src/pages/` and are registered in `web/src/App.tsx`; run `npm run build` and commit `clue/web/static`.

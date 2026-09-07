# Extending the harness

## Add an LLM provider
`clue/agents/llm_client.py`
```python
class MyClient:
    model: str
    def complete(self, system: str, messages: list[dict[str, str]], temperature: float = 0.2) -> LLMResponse:
        ...  # return LLMResponse(text=..., raw=..., usage=...)
```
Register in `make_client`: `if provider == "my": return MyClient(model, os.environ["MY_API_KEY"])`.
Select with `CLUE_LLM_PROVIDER=my` or `--provider my`. Anything speaking the OpenAI chat-completions format
needs no code: use `provider=local` with `OPENAI_BASE_URL`.

### Native function calling (optional)
`LLMPlayerAgent` currently pre-computes tools into the prompt (one round-trip per decision, deterministic
cost). To let a model call tools itself: pass `TOOL_SPECS` (from `clue.tools`) to your provider, loop on
tool-call responses and dispatch to `LLMPlayerAgent._tool(obs, name, **args)`, which already logs calls.

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
Everything a UI needs is `GameManager.get_observation(pid)`, `legal_actions(pid)`, `step(action)` and
`export_replay(viewer)`. The TUI (`clue/tui/app.py`) is ~300 lines on top of these; a FastAPI server would
expose the same four calls and run `run_game` in a background task with a queue-backed agent exactly like
`TUIHumanAgent`.

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
pytest -q                     # 98 tests incl. headless TUI, solver, expert bot, glue/CLI (~6 min); pytest -n is not used, use --workers in tournaments instead
pytest -q tests/test_rules.py # engine only (~2 s)
ruff format . && ruff check . && mypy clue
python eval/make_demo.py            # regenerate demo_game.md
python eval/make_tui_screenshot.py  # regenerate docs/tui_screenshot.*
python -m clue eval --games 50      # regenerate eval/report.md + charts.png
```
Invariants to preserve: `clue.rules` imports nothing outside itself; the manager contains no strategy text;
every action applied goes through `rules.is_legal`; every private datum is carried in `Event.private` with
an explicit `private_to`.

## Web UI

Backend routes live in `clue/web/routes/*.py`; every outbound game payload goes through `GameSession.render_*`
(keep it that way - the privacy test in `tests/test_web.py` checks frames, not routes). New frontend pages go in
`web/src/pages/` and are registered in `web/src/App.tsx`; run `npm run build` and commit `clue/web/static`.

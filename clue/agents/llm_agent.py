"""LLMPlayerAgent: base prompt + optional strategy fragment + symbolic tools + JSON validation.

Flow per decision: build compact observation -> (tools) precompute analysis -> ask LLM -> parse JSON ->
validate against legal_actions -> on failure, retry once with the error -> else fall back to the
heuristic bot (logged). Every prompt/response/tool call is logged to the manager for audit.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from clue.agents.base import PlayerAgent, PonderContext
from clue.agents.base import PonderInterrupted as PonderInterrupted_
from clue.agents.baselines import BaselineHeuristicBot
from clue.agents.llm_client import BudgetExceeded, LLMClient, ToolCall, extract_json, make_client
from clue.manager.notebook import Notebook
from clue.rules import Action
from clue.tools import (
    TOOL_SPECS,
    can_accuse_confidently,
    get_possible_solutions,
    get_unseen_cards,
    hard_deductions,
    holder_probabilities,
    opponent_threat,
    solution_probabilities,
    suggestion_ev,
    update_notebook,
)

BASE_PROMPT_PATH = Path(__file__).with_name("base_prompt.md")


def variant_notes(cfg: dict[str, Any], you: dict[str, Any]) -> list[str]:
    """Plain-language reminders for any opt-in variant in effect (docs/variants.md); empty for classic rules."""
    out: list[str] = []
    if cfg.get("teams"):
        mates = [q for q in (you.get("team") or []) if q != you.get("id")]
        out.append(f"TEAM PLAY: you and {', '.join(mates)} share hands (already merged into your notebook) and win together; teammates never disprove each other.")
    if cfg.get("private_disproofs"):
        out.append(
            "PRIVATE DISPROOFS: you only learn who passed / who showed a card in suggestions you (or a teammate) made or were asked to disprove; "
            "other disproofs only tell you that *someone* showed a card."
        )
    if cfg.get("wrong_accusation") == "skip_turns":
        out.append(f"WRONG ACCUSATION PENALTY: a wrong accusation does not eliminate you; you sit out your next {cfg.get('accusation_penalty_turns', 2)} turn(s) instead (you still must disprove).")
    return out


PONDER_PROMPT_PATH = Path(__file__).with_name("ponder_prompt.md")


def load_strategy(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        alt = Path("strategies") / (p.name if p.suffix else f"{p.name}.md")
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"strategy file not found: {path}")
    return p.read_text()


class LLMPlayerAgent(PlayerAgent):
    kind = "llm"
    supports_ponder = True

    def __init__(
        self,
        player_id: str,
        client: LLMClient | None = None,
        model: str | None = None,
        provider: str | None = None,
        strategy_path: str | None = None,
        temperature: float = 0.2,
        use_tools: bool = True,
        seed: int = 0,
        history_limit: int = 40,
        tool_mode: str | None = None,
        prompt_profile: str = "full",
        max_tool_rounds: int = 4,
    ) -> None:
        super().__init__(player_id)
        self.client = client or make_client(provider, model)
        self.model = getattr(self.client, "model", model or "mock")
        self.temperature = temperature
        # tool_mode: "precomputed" (analysis bundle in the prompt), "native" (model calls tools via function
        # calling; analysis still precomputed as a floor), "none" (ablation). `use_tools=False` == "none".
        self.tool_mode = "none" if not use_tools else (tool_mode or "precomputed")
        self.use_tools = self.tool_mode != "none"
        self.prompt_profile = prompt_profile  # "full" | "compact" (drops public_history, trims notebook)
        self.max_tool_rounds = max_tool_rounds
        self.strategy_path = strategy_path
        self.strategy_text = load_strategy(strategy_path)
        self.system_prompt = BASE_PROMPT_PATH.read_text() + ("\n\n# STRATEGY\n" + self.strategy_text if self.strategy_text else "")
        self.fallback = BaselineHeuristicBot(player_id, seed=seed)
        self.rng = random.Random(seed)
        self.history_limit = history_limit
        self.stats = {"calls": 0, "valid_first_try": 0, "retries": 0, "fallbacks": 0, "ponder_rounds": 0, "native_tool_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self.cost_usd = 0.0
        self.max_ponder_rounds = 5
        self.last_plan: str | None = None

    # ------------------------------------------------------------------ helpers
    def _ctx(self, obs: dict[str, Any]) -> tuple[Notebook, list[str], dict[str, int], str]:
        nb = obs.get("_notebook_obj") or Notebook(**obs["notebook"])
        players = [p["id"] for p in obs["board"]["players"]]
        sizes = {p["id"]: p["hand_size"] for p in obs["board"]["players"]}
        return nb, players, sizes, obs["config"]["edition"]

    def _log(self, obs: dict[str, Any], kind: str, **data: Any) -> None:
        gm = obs.get("_manager")
        if gm is not None:
            gm.log_agent_note(self.id, {"summary": kind, **data})

    def _tool(self, obs: dict[str, Any], name: str, **args: Any) -> Any:
        nb, players, sizes, edition = self._ctx(obs)
        if name == "get_unseen_cards":
            res: Any = get_unseen_cards(nb, edition)
        elif name == "get_possible_solutions":
            res = [list(c) for c in get_possible_solutions(nb, players, sizes, edition)]
        elif name == "solution_probabilities":
            res = solution_probabilities(nb, players, sizes, edition, rng=self.rng)
        elif name == "suggestion_ev":
            res = suggestion_ev(nb, players, self.id, args["suspect"], args["weapon"], args["room"], edition)
        elif name == "can_accuse_confidently":
            res = can_accuse_confidently(nb, players, args.get("threshold", 0.9), sizes, edition)
        elif name == "update_notebook":
            res = update_notebook(nb, args["note"])
        elif name == "holder_probabilities":
            res = holder_probabilities(nb, players, sizes, edition)
        elif name == "hard_deductions":
            res = hard_deductions(nb, players, sizes, edition)
        elif name == "opponent_threat":
            elim = {p["id"] for p in obs["board"]["players"] if p.get("eliminated")}
            res = opponent_threat(nb, players, self.id, sizes, edition, obs.get("public_history", []), elim)
        else:
            raise KeyError(name)
        gm = obs.get("_manager")
        if gm is not None:
            gm.log_tool_call(self.id, name, args, res)
        return res

    def _analysis(self, obs: dict[str, Any], legal: list[Action]) -> dict[str, Any]:
        """Pre-computed tool bundle injected into the prompt (only when tools are enabled)."""
        unseen = self._tool(obs, "get_unseen_cards")
        post = self._tool(obs, "solution_probabilities")
        verdict = self._tool(obs, "can_accuse_confidently", threshold=0.9)
        certain = self._tool(obs, "hard_deductions")
        threat = self._tool(obs, "opponent_threat")
        out: dict[str, Any] = {"unseen_cards": unseen, "posterior": post, "accusation_check": verdict, "certain_facts": certain, "opponent_threat": threat}
        if any(a.type == "suggest" for a in legal):
            room = obs["you"]["position"]
            nb, players, _, edition = self._ctx(obs)
            ranked = []
            for s in unseen["suspects"] or obs["cards"]["suspects"]:
                for w in unseen["weapons"] or obs["cards"]["weapons"]:
                    ev = suggestion_ev(nb, players, self.id, s, w, room, edition)
                    ranked.append((ev["score"], s, w, ev))
            ranked.sort(key=lambda x: -x[0])
            out["top_suggestions"] = [{"suspect": s, "weapon": w, **ev} for _, s, w, ev in ranked[:5]]
            if ranked:
                gm = obs.get("_manager")
                if gm is not None:
                    gm.log_tool_call(self.id, "suggestion_ev", {"room": room, "batch": len(ranked)}, out["top_suggestions"])
        return out

    def _compact_obs(self, obs: dict[str, Any], legal: list[Action]) -> dict[str, Any]:
        o = {k: v for k, v in obs.items() if not k.startswith("_")}
        o["public_history"] = o["public_history"][-self.history_limit :]
        notes = variant_notes(obs.get("config", {}), obs.get("you", {}))
        if notes:
            o["house_rules"] = notes
        if self.prompt_profile == "compact":
            # the notebook + analysis already summarise the history; keep only the last few events
            o["public_history"] = o["public_history"][-6:]
            o["board"] = {k: v for k, v in o["board"].items() if k in ("your_legal_moves", "players", "secret_passages")}
            nb = dict(o["notebook"])
            nb.pop("suggestions_made", None)
            nb.pop("disproof_counts", None)
            nb.pop("my_suggestions", None)
            nb["has_one_of"] = [{"player": c["player"], "cards": c["cards"]} for c in nb.get("has_one_of", [])]
            nb["unrefuted_suggestions"] = [{"player": c["player"], "cards": c["cards"]} for c in nb.get("unrefuted_suggestions", [])]
            o["notebook"] = nb
        moves = [a for a in legal if a.type == "move"]
        others = [a.model_dump(exclude_none=True) for a in legal if a.type not in ("move", "suggest")]
        o["legal_actions"] = others + [a.model_dump(exclude_none=True) for a in moves]
        if any(a.type == "suggest" for a in legal):
            o["legal_actions"].append({"type": "suggest", "player": self.id, "room": obs["you"]["position"], "suspect": "<any suspect>", "weapon": "<any weapon>"})
        return o

    def _recommended(self, obs: dict[str, Any], legal: list[Action]) -> dict[str, Any]:
        rec = self.fallback.choose_action(obs, legal)
        return rec.model_dump(exclude_none=True)

    def _account(self, resp: Any) -> None:
        self.stats["prompt_tokens"] += int(resp.usage.get("prompt_tokens", 0) or 0)
        self.stats["completion_tokens"] += int(resp.usage.get("completion_tokens", 0) or 0)
        self.cost_usd += float(getattr(resp, "cost_usd", 0.0) or 0.0)

    def _native_tool_loop(self, obs: dict[str, Any], messages: list[dict[str, Any]]) -> Any:
        """Let the model call symbolic tools via function calling, up to max_tool_rounds, then return the final reply."""
        specs = [t for t in TOOL_SPECS if t["name"] != "update_notebook"] + [t for t in TOOL_SPECS if t["name"] == "update_notebook"]
        for _round in range(self.max_tool_rounds + 1):
            resp = self.client.complete(self.system_prompt, messages, self.temperature, tools=specs if _round < self.max_tool_rounds else None, json_mode=_round >= self.max_tool_rounds)
            self._account(resp)
            if not resp.tool_calls:
                return resp
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.text or None,
                    "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.args)}} for tc in resp.tool_calls],
                }
            )
            for tc in resp.tool_calls:
                self.stats["native_tool_calls"] += 1
                result = self._safe_tool(obs, tc)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, separators=(",", ":"), default=str)[:6000]})
        return resp

    def _safe_tool(self, obs: dict[str, Any], tc: ToolCall) -> Any:
        try:
            return self._tool(obs, tc.name, **tc.args)
        except KeyError:
            return {"error": f"unknown tool {tc.name}", "available": [t["name"] for t in TOOL_SPECS]}
        except TypeError as e:
            return {"error": str(e)}

    def _ask(self, obs: dict[str, Any], user_payload: dict[str, Any], hint: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        content = json.dumps(user_payload, separators=(",", ":"))
        content += f"\n<recommended_action>{json.dumps(hint)}</recommended_action>" if hint else ""
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
        last_err = ""
        for attempt in range(2):
            self.stats["calls"] += 1
            try:
                if self.tool_mode == "native" and attempt == 0:
                    resp = self._native_tool_loop(obs, messages)
                else:
                    resp = self.client.complete(self.system_prompt, messages, self.temperature, json_mode=True)
                    self._account(resp)
                parsed = extract_json(resp.text)
                self._log(
                    obs, "llm_response", attempt=attempt, text=resp.text[:4000], usage=resp.usage, model=self.model, cached=getattr(resp, "cached", False), cost_usd=getattr(resp, "cost_usd", 0.0)
                )
                if attempt == 0:
                    self.stats["valid_first_try"] += 1
                return parsed, resp.text
            except BudgetExceeded:
                raise  # a spend cap must stop the run, never silently degrade to heuristic play
            except Exception as e:  # network, parse
                last_err = str(e)
                self._log(obs, "llm_error", attempt=attempt, error=last_err)
                self.stats["retries"] += 1
                messages.append({"role": "assistant", "content": getattr(locals().get("resp"), "text", "")})
                messages.append({"role": "user", "content": f"error: {last_err}. Reply with ONLY a valid JSON object as specified."})
        return None, last_err

    # ------------------------------------------------------------------ interface
    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        obs = observation
        payload = self._compact_obs(obs, legal_actions)
        if obs.get("last_error"):
            payload["error"] = obs["last_error"]
        if obs.get("ponder_summary"):
            payload["ponder_summary"] = obs["ponder_summary"]
        if self.last_plan:
            payload["your_plan_from_pondering"] = self.last_plan
        hint = self._recommended(obs, legal_actions) if self.use_tools else {}
        if self.use_tools:
            payload["analysis"] = self._analysis(obs, legal_actions)
            payload["analysis"]["recommended_action"] = hint
        parsed, raw = self._ask(obs, payload, hint)
        if parsed is None:
            return self._fallback_action(obs, legal_actions, f"no valid JSON: {raw}")
        try:
            act = Action(**{**parsed.get("action", {}), "player": self.id})
        except Exception as e:
            act = self._fallback_action(obs, legal_actions, f"bad action schema: {e}")
        if act.type == "accuse":
            if not obs["can_accuse"]:
                return self._fallback_action(obs, legal_actions, "accuse not allowed now")
        elif act not in legal_actions:
            # try tolerant match (LLM may drop optional fields)
            match = [a for a in legal_actions if a.type == act.type and (a.to == act.to) and (a.suspect == act.suspect) and (a.weapon == act.weapon)]
            if len(match) == 1:
                act = match[0]
            else:
                return self._fallback_action(obs, legal_actions, f"{act.key()} not in legal_actions")
        if note := parsed.get("note"):
            self._tool(obs, "update_notebook", note=str(note))
        return act

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        obs = observation
        default = self.fallback.choose_card_to_show(obs, cards_that_can_disprove)  # also tracks what we've shown
        if len(cards_that_can_disprove) == 1:
            return cards_that_can_disprove[0]
        payload = self._compact_obs(obs, [])
        payload["decision"] = "disprove"
        payload["cards_that_can_disprove"] = cards_that_can_disprove
        payload["suggester"] = obs["turn"]["pending_suggestion"]["suggester"]
        parsed, _ = self._ask(obs, payload, {"card": default})
        if parsed and parsed.get("card") in cards_that_can_disprove:
            return str(parsed["card"])
        self.stats["fallbacks"] += 1
        self._log(obs, "fallback_card", card=default)
        return default

    # ------------------------------------------------------------------ pondering
    def ponder(self, observation: dict[str, Any], ctx: PonderContext) -> dict[str, Any]:
        """Bounded think -> tool -> think loop on a snapshot. Interruptible between every LLM/tool call."""
        obs = observation
        payload = self._compact_obs(obs, [])
        payload["mode"] = "ponder"
        payload["ponder_summary"] = {"previous_plan": self.last_plan, "notes": obs["notebook"].get("notes", [])[-5:]}
        if self.use_tools:
            payload["analysis"] = {"unseen_cards": ctx.tool("get_unseen_cards")}
        system = self.system_prompt + "\n\n" + PONDER_PROMPT_PATH.read_text()
        messages = [{"role": "user", "content": json.dumps(payload, separators=(",", ":"))}]
        result: dict[str, Any] = {"rounds": 0}
        for _ in range(self.max_ponder_rounds):
            ctx.check()
            ctx.rounds += 1
            self.stats["ponder_rounds"] += 1
            try:
                resp = self.client.complete(system, messages, self.temperature, json_mode=True)
                self._account(resp)
                ctx.check()  # a stop may have arrived during the network call
                parsed = extract_json(resp.text)
            except Exception as e:
                if isinstance(e, PonderInterrupted_ | BudgetExceeded):
                    raise
                result["error"] = str(e)
                break
            messages.append({"role": "assistant", "content": resp.text})
            if parsed.get("tool") and self.use_tools:
                name = str(parsed["tool"])
                args = parsed.get("args") or {}
                try:
                    out = ctx.tool(name, **args)
                except KeyError:
                    out = {"error": f"unknown tool {name}"}
                except TypeError as e:
                    out = {"error": str(e)}
                if name == "update_notebook" and "note" in args:
                    ctx.note(str(args["note"]))
                messages.append({"role": "user", "content": json.dumps({"tool_result": out}, separators=(",", ":"))})
                continue
            for n in parsed.get("notes") or []:
                ctx.note(str(n))
            if parsed.get("plan"):
                self.last_plan = str(parsed["plan"])
                result["plan"] = self.last_plan
            result["thought"] = str(parsed.get("thought", ""))[:500]
            break
        result["rounds"] = ctx.rounds
        return result

    def export_state(self) -> dict[str, Any]:
        return {**super().export_state(), "stats": dict(self.stats), "cost_usd": self.cost_usd, "last_plan": self.last_plan, "fallback": self.fallback.export_state()}

    def import_state(self, state: dict[str, Any]) -> None:
        super().import_state(state)
        self.stats.update(state.get("stats", {}))
        self.cost_usd = float(state.get("cost_usd", 0.0))
        self.last_plan = state.get("last_plan")
        self.fallback.import_state(state.get("fallback", {}))

    def _fallback_action(self, obs: dict[str, Any], legal: list[Action], reason: str) -> Action:
        self.stats["fallbacks"] += 1
        act = self.fallback.choose_action(obs, legal)
        self._log(obs, "fallback_to_heuristic", reason=reason, action=act.model_dump(exclude_none=True))
        return act

"""CLI: python -m clue play|tournament|replay|eval"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

from clue.agents.factory import make_agent, parse_players_arg
from clue.agents.human import describe_event
from clue.config import load_yaml_config
from clue.eval.tournament import markdown_table, run_tournament, write_csv
from clue.manager import GameManager, PlayerSpec
from clue.manager.runner import run_game
from clue.rules import GameConfig

app = typer.Typer(help="Clue / Cluedo AI harness", no_args_is_help=True)
console = Console()
_YAML_EXTRA: dict[str, Any] = {}


def parse_variants(arg: str, ids: list[str]) -> dict[str, Any]:
    """`--variants` grammar: comma list of  private | skip[=N] | shuffle | teams[=K]  (teams=K forms K teams round-robin
    over the seats; default 2). See docs/variants.md."""
    out: dict[str, Any] = {}
    for tok in filter(None, (t.strip() for t in arg.split(","))):
        key, _, val = tok.partition("=")
        if key == "private":
            out["private_disproofs"] = True
        elif key == "skip":
            out["wrong_accusation"] = "skip_turns"
            if val:
                out["accusation_penalty_turns"] = int(val)
        elif key == "shuffle":
            out["shuffle_seats"] = True
        elif key == "teams":
            k = int(val or 2)
            out["teams"] = [ids[i::k] for i in range(k)]
        else:
            raise typer.BadParameter(f"unknown variant {key!r}; use private | skip[=N] | shuffle | teams[=K]")
    return out


def _specs(
    config: Optional[str],
    players: Optional[str],
    seed: Optional[int],
    dice: Optional[int],
    strategy: Optional[str],
    no_tools: bool,
    tool_mode: Optional[str] = None,
    prompt_profile: Optional[str] = None,
    edition: Optional[str] = None,
    variants: Optional[str] = None,
) -> tuple[GameConfig, list[PlayerSpec], int]:
    if config:
        cfg, specs, cseed, raw = load_yaml_config(config)
        seed = cseed if seed is None else seed
        _YAML_EXTRA.update({k: raw[k] for k in ("ponder", "workers") if k in raw})
    elif players:
        specs = parse_players_arg(players)
        cfg = GameConfig(num_players=len(specs))
        seed = seed or 0
    else:
        raise typer.BadParameter("provide --config or --players")
    if edition:
        from clue.config import EDITION_ALIASES

        if edition not in EDITION_ALIASES:
            raise typer.BadParameter(f"unknown edition {edition!r}; choose classic | modern | large")
        cfg = cfg.model_copy(update={"edition": EDITION_ALIASES[edition]})
    from clue.rules.cards import max_players

    if not 3 <= cfg.num_players <= max_players(cfg.edition):
        raise typer.BadParameter(f"{cfg.edition} edition needs 3..{max_players(cfg.edition)} players (got {cfg.num_players}); use --edition large for up to 12")
    if dice:
        cfg = cfg.model_copy(update={"dice": dice})
    if variants:
        cfg = cfg.model_copy(update=parse_variants(variants, [s.id for s in specs]))
    if strategy:
        specs = [s.model_copy(update={"strategy": strategy}) if s.kind == "llm" and not s.strategy else s for s in specs]
    if no_tools:
        specs = [s.model_copy(update={"tools": False}) if s.kind == "llm" else s for s in specs]
    if tool_mode:
        specs = [s.model_copy(update={"tool_mode": tool_mode, "tools": tool_mode != "none"}) if s.kind == "llm" else s for s in specs]
    if prompt_profile:
        specs = [s.model_copy(update={"prompt_profile": prompt_profile}) if s.kind == "llm" else s for s in specs]
    specs = _resolve_models(specs)
    return cfg, specs, seed or 0


def _resolve_models(specs: list[PlayerSpec]) -> list[PlayerSpec]:
    """Fill LLM seats' model from env (CLUE_LLM_MODEL / provider) so labels & replays name the real model."""
    from clue.agents.llm_client import _load_dotenv

    _load_dotenv()
    provider = (os.getenv("CLUE_LLM_PROVIDER") or "mock").lower()
    default = os.getenv("CLUE_LLM_MODEL") or "mock"
    if provider == "mock":
        default = "mock"
    return [s.model_copy(update={"model": default}) if s.kind == "llm" and not s.model else s for s in specs]


def _budget(max_usd: Optional[float]) -> None:
    from clue.agents.llm_client import configure_budget

    configure_budget(max_usd)


def _print_cost() -> None:
    from clue.agents.llm_client import GLOBAL_COST

    if GLOBAL_COST.calls:
        console.print(f"[dim]LLM usage: {GLOBAL_COST.summary()}[/dim]")


@app.command()
def play(
    config: Optional[str] = typer.Option(None, help="game.yaml"),
    players: Optional[str] = typer.Option(None, help="e.g. human,llm:bayesian,llm:aggressive,baseline"),
    seed: Optional[int] = typer.Option(None),
    dice: Optional[int] = typer.Option(None, help="1 or 2"),
    edition: Optional[str] = typer.Option(None, "--edition", help="classic | modern | large (12 suspects/weapons/rooms, up to 12 players)"),
    variants: Optional[str] = typer.Option(None, "--variants", help="comma list: private | skip[=N] | shuffle | teams[=K] (docs/variants.md)"),
    strategy: Optional[str] = typer.Option(None, help="default strategy .md for LLM seats without one"),
    no_tools: bool = typer.Option(False, "--no-tools", help="ablation: LLM agents get no symbolic analysis"),
    provider: Optional[str] = typer.Option(None, help="mock|openrouter|openai|local|anthropic (default env CLUE_LLM_PROVIDER)"),
    replay_dir: str = typer.Option("replays"),
    quiet: bool = typer.Option(False, "--quiet"),
    ui: str = typer.Option("auto", help="tui | cli | auto (tui when a human or --spectate; plain text otherwise)"),
    spectate: bool = typer.Option(False, "--spectate", help="watch an all-AI game in the TUI"),
    delay: float = typer.Option(0.6, help="seconds between AI events in the TUI"),
    no_emoji: bool = typer.Option(False, "--no-emoji", help="use letters S/M/W/G/K/P instead of symbols for tokens"),
    ponder: bool = typer.Option(False, "--ponder", help="let idle AI players think in parallel between turns"),
    ponder_grace: float = typer.Option(2.0, help="max seconds to wait for a pondering agent when its turn begins"),
    tool_mode: Optional[str] = typer.Option(None, "--tool-mode", help="LLM agents: precomputed | native | none"),
    prompt_profile: Optional[str] = typer.Option(None, "--prompt-profile", help="LLM agents: full | compact"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd", help="hard cap on live LLM spend for this run"),
    resume: Optional[str] = typer.Option(None, "--resume", help="continue a saved game (.json written by --save/--autosave or ctrl+s in the TUI)"),
    save: Optional[str] = typer.Option(None, "--save", help="checkpoint file, rewritten after every action (default: saves/game_<seed>.json in the TUI)"),
    no_autosave: bool = typer.Option(False, "--no-autosave", help="disable the TUI's automatic checkpoint"),
) -> None:
    """Play one game: interactive (TUI or plain CLI), spectated, or fully automated. Resume with --resume FILE."""
    _budget(max_usd)
    if resume:
        gm = GameManager.load(resume)
        cfg, specs, seed = gm.config, gm.specs, gm.seed
        if gm.finished:
            raise typer.BadParameter(f"{resume} is a finished game")
    else:
        cfg, specs, seed = _specs(config, players, seed, dice, strategy, no_tools, tool_mode, prompt_profile, edition, variants)
    ponder = ponder or bool(_YAML_EXTRA.get("ponder"))
    has_human = any(s.kind == "human" for s in specs)
    if ui == "auto":
        ui = "tui" if (has_human or spectate) else "cli"
    if not resume:
        gm = GameManager.create(specs, seed=seed, config=cfg)
    agents = {s.id: make_agent(s, seed=seed + i, provider=provider, ui=ui) for i, s in enumerate(specs)}
    if resume:
        restored = gm.restore_agents(agents)
        console.print(f"[bold]Resumed[/bold] {resume}: turn {gm.state.turn_number}, {len(gm.events)} events, agent memory restored for {', '.join(restored) or 'nobody'}")
    autosave: Optional[str] = save or (resume if resume else None)
    if autosave is None and ui == "tui" and not no_autosave:
        autosave = f"saves/game_{seed}.json"
    if ui == "tui":
        from clue.tui.app import run_tui

        run_tui(gm, agents, delay=delay, emoji=not no_emoji, ponder=ponder, ponder_grace=ponder_grace, autosave=autosave)
        if not gm.finished:
            console.print(f"game not finished - resume with: clue play --resume {autosave or '<save file>'}")
            return
    else:
        console.print(f"[bold]Clue[/bold] seed={seed} dice={cfg.dice} players: " + ", ".join(f"{s.id}={s.label()}" for s in specs))

        def on_events(g: GameManager, evs: list[dict[str, Any]]) -> None:
            if has_human or quiet:
                return  # human agent prints redacted events itself
            for e in evs:
                console.print(describe_event(e))

        run_game(gm, agents, on_events, ponder=ponder, ponder_grace=ponder_grace, autosave=autosave)
    s = gm.summary()
    console.print(f"\n[bold green]Winner: {s['winner']}[/bold green]  solution={s['solution']} turns={s['turns']}")
    p = gm.write_replay(Path(replay_dir) / f"game_{seed}.jsonl")
    for pid in gm.player_ids():
        gm.write_replay(Path(replay_dir) / f"game_{seed}_redacted_{pid}.json", viewer=pid)
    console.print(f"replay: {p}  hash={gm.replay_hash()[:16]}")
    for pid, ag in agents.items():
        st = getattr(ag, "stats", None)
        if st:
            console.print(f"{pid} llm stats: {st}")
    if ponder:
        for pid, ps in gm.ponder_stats.items():
            console.print(f"{pid} ponder: {ps}")


@app.command()
def tournament(
    games: int = typer.Option(20),
    players: Optional[str] = typer.Option(None),
    config: Optional[str] = typer.Option(None),
    seed: int = typer.Option(0),
    dice: Optional[int] = typer.Option(None),
    edition: Optional[str] = typer.Option(None, "--edition", help="classic | modern | large"),
    variants: Optional[str] = typer.Option(None, "--variants", help="comma list: private | skip[=N] | shuffle | teams[=K] (docs/variants.md)"),
    no_tools: bool = typer.Option(False, "--no-tools"),
    provider: Optional[str] = typer.Option(None),
    report: str = typer.Option("elo.csv"),
    replay_dir: Optional[str] = typer.Option(None),
    ponder: bool = typer.Option(False, "--ponder"),
    tool_mode: Optional[str] = typer.Option(None, "--tool-mode", help="LLM agents: precomputed | native | none"),
    prompt_profile: Optional[str] = typer.Option(None, "--prompt-profile", help="LLM agents: full | compact"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd", help="hard cap on live LLM spend for this run"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="games played concurrently: N, 0 = all CPU cores (default 1; YAML `workers:`)"),
    duplicate: bool = typer.Option(False, "--duplicate", help="duplicate-deal blocks: same deal, agents rotated through every seat; paired stats"),
) -> None:
    """Run N AI-vs-AI games (optionally in parallel) and write win-rate / ELO stats."""
    cfg, specs, seed = _specs(config, players, seed, dice, None, no_tools, tool_mode, prompt_profile, edition, variants)
    _budget(max_usd)
    if workers is None:
        workers = int(_YAML_EXTRA.get("workers", 1))
    from clue.eval.tournament import resolve_workers

    console.print(f"[dim]{games} games, {min(resolve_workers(workers), games)} in parallel[/dim]")
    try:
        rep = run_tournament(specs, games, seed=seed, config=cfg, provider=provider, replay_dir=replay_dir, verbose=True, ponder=ponder, workers=workers, duplicate=duplicate)
    finally:
        _print_cost()
    console.print(markdown_table(rep))
    if "duplicate" in rep:
        console.print(f"[bold]duplicate deals[/bold] ({rep['duplicate']['deals']} deals × {len(specs)} rotations)")
        for lab, d in rep["duplicate"]["per_label"].items():
            console.print(f"  {lab}: win share {d['win_share']:.3f}" + (f"  vs {d['vs']}: {d['paired_diff']:+.3f} ± {d['se']:.3f}" if "vs" in d else ""))
    write_csv(rep, report)
    Path(report).with_suffix(".json").write_text(json.dumps(rep, indent=1))
    console.print(f"wrote {report}")


@app.command("live-eval")
def live_eval(
    model: Optional[str] = typer.Option(None, help="model id (default env CLUE_LLM_MODEL, e.g. openrouter/free)"),
    games: int = typer.Option(5, help="paired seeds per variant"),
    seed: int = typer.Option(0),
    out: str = typer.Option("eval/live"),
    max_usd: float = typer.Option(0.25, "--max-usd", help="hard spend cap for the whole run"),
    provider: str = typer.Option("openrouter"),
    brackets: str = typer.Option("ablation,ponder", help="comma list: ablation, ponder"),
    prompt_profile: str = typer.Option("compact", "--prompt-profile"),
    workers: int = typer.Option(1, "--workers", "-w", help="concurrent games per bracket (threads; the spend cap is shared)"),
) -> None:
    """Live LLM eval: tool-mode ablation + ponder brackets on paired seeds vs expert+heuristic; Wilson CIs; cost cap."""
    from clue.eval.live_eval import run_live_eval

    specs = _resolve_models([PlayerSpec(id="P1", kind="llm", model=model)])
    run_live_eval(
        specs[0].model or "mock", games, seed=seed, out_dir=out, max_usd=max_usd, provider=provider, brackets=tuple(b.strip() for b in brackets.split(",")), profile=prompt_profile, workers=workers
    )
    console.print(Path(out, "live_report.md").read_text())
    _print_cost()


@app.command()
def replay(
    path: str,
    viewer: Optional[str] = typer.Option(None, help="player id to redact for"),
    tui: bool = typer.Option(False, "--tui", help="step through the replay in the TUI viewer"),
    no_emoji: bool = typer.Option(False, "--no-emoji"),
) -> None:
    """Pretty-print a replay JSONL, or step through it in the TUI (--tui)."""
    if tui:
        from clue.tui.replay_viewer import run_replay_viewer

        run_replay_viewer(path, emoji=not no_emoji)
        return
    for line in Path(path).read_text().splitlines():
        rec = json.loads(line)
        if rec["kind"] == "event":
            console.print(describe_event(rec))
        elif rec["kind"] == "tool_call":
            console.print(f"[cyan]  tool {rec['player']}.{rec['tool']}({rec['args']})[/cyan]")
        elif rec["kind"] == "agent_note":
            console.print(f"[magenta]  note {rec['player']}: {rec['summary']}[/magenta]")


@app.command()
def eval(games: int = typer.Option(50), seed: int = typer.Option(0), out: str = typer.Option("eval"), live: bool = typer.Option(False, "--live")) -> None:
    """Baseline vs Heuristic vs LLM+tools vs LLM no-tools; writes report.md + charts.png."""
    from clue.eval.report import run_eval

    run_eval(games=games, seed=seed, out_dir=out, live=live)


@app.command()
def web(
    host: str = typer.Option("0.0.0.0", help="bind address (0.0.0.0 = reachable on the LAN)"),
    port: int = typer.Option(8000),
    hotseat: bool = typer.Option(False, "--hotseat", help="allow several human seats sharing one browser (pass the device)"),
    no_remote: bool = typer.Option(False, "--no-remote", help="disable remote seats (one invite link per human, several browsers)"),
    replay_dir: str = typer.Option("replays"),
    saves_dir: str = typer.Option("saves"),
    open_browser: bool = typer.Option(False, "--open", help="open the UI in a browser"),
    dev_origin: Optional[str] = typer.Option(None, help="CORS origin for the Vite dev server, e.g. http://localhost:5173"),
    max_usd: Optional[float] = typer.Option(None, "--max-usd", help="hard cap on live LLM spend for the whole server"),
) -> None:
    """Serve the web UI (React) + REST/WebSocket API. Requires `pip install -e ".[web]"`."""
    try:
        from clue.web.server import serve
        from clue.web.settings import WebSettings
    except ImportError as e:  # pragma: no cover
        raise typer.BadParameter(f"web extras not installed: pip install -e '.[web]' ({e})") from e
    _budget(max_usd)
    st = WebSettings(host=host, port=port, hotseat=hotseat, remote=not no_remote, replay_dir=Path(replay_dir), saves_dir=Path(saves_dir), dev_origin=dev_origin)
    console.print(f"[bold]Clue web UI[/bold] http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/  (API docs at /api/docs)")
    serve(st, open_browser=open_browser)


if __name__ == "__main__":
    app()

"""Human CLI adapter. Same PlayerAgent interface as bots/LLMs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from clue.agents.base import PlayerAgent
from clue.rules import Action
from clue.rules import board as B

console = Console()


def describe_event(e: dict[str, Any]) -> str:
    t = e["type"]
    p = e.get("player")
    if t == "roll":
        return f"{p} rolled {e['dice']} = {e['total']}"
    if t == "move":
        return f"{p} moved {e['from']} -> {e['to']}"
    if t == "passage":
        return f"{p} took the secret passage {e['from']} -> {e['to']}"
    if t == "suggest":
        return f"{p} suggests: {e['suspect']} with the {e['weapon']} in the {e['room']}"
    if t == "cannot_disprove":
        return f"  {p} cannot disprove"
    if t == "can_disprove":
        return f"  {p} can disprove..."
    if t == "disproved":
        card = e.get("card")
        return f"  {e.get('disprover') or p or 'someone'} showed {'the ' + card if card else 'a card'} to {e['suggester']}"
    if t == "penalised":
        return f"{p} was wrong and sits out the next {e.get('skip_turns')} turn(s)"
    if t == "turn_skipped":
        return f"--- Turn {e['turn']}: {p} sits out ({e.get('remaining')} more) ---"
    if t == "no_one_disproved":
        return "  NOBODY could disprove!"
    if t == "accuse":
        return f"{p} ACCUSES {e['suspect']} / {e['weapon']} / {e['room']} -> {'CORRECT' if e['correct'] else 'WRONG'}"
    if t == "eliminated":
        return f"{p} is eliminated (still must show cards)"
    if t == "game_over":
        return f"GAME OVER. Winner: {e.get('winner')}. Solution: {e.get('solution')}"
    if t == "turn_start":
        return f"--- Turn {e['turn']}: {p} ---"
    if t == "game_start":
        ps = e.get("players") or []
        return f"Game start (seed {e.get('seed')}): " + ", ".join(f"{q.get('id')} {q.get('kind')}{':' + q['bot'] if q.get('bot') else ''}" for q in ps if isinstance(q, dict))
    if t == "boxed_in":
        return f"{p} is boxed in and cannot move"
    return f"{t} {e}"


class HumanCLIAgent(PlayerAgent):
    kind = "human"

    def __init__(self, player_id: str, input_fn: Callable[[str], str] = input) -> None:
        super().__init__(player_id)
        self.input_fn = input_fn

    def on_event(self, event: dict[str, Any]) -> None:
        if event["type"] in ("game_start",):
            return
        console.print(f"[dim]{describe_event(event)}[/dim]")

    def _show(self, obs: dict[str, Any]) -> None:
        sus = obs["cards"]["suspects"]
        labels = dict(zip(sus, "SMWGKPBYHATR"[: len(sus)], strict=True))  # Scarlet Mustard White Green peacocK Plum Butler Yvette peacH grAy boddy(T) Rose
        key = ", ".join(f"{lab}={s}" for s, lab in labels.items())
        console.print(Panel(B.ascii_board(obs["board"]["token_positions"], labels, obs["config"]["edition"]), title=f"Board (+ = door, X = cellar, tokens: {key})", expand=False))
        you = obs["you"]
        console.print(f"[bold]You are {you['id']} ({you['suspect_token']})[/bold] at {you['position']}  hand: [green]{', '.join(you['hand'])}[/green]")
        nb = obs["notebook"]
        t = Table(title="Notebook", show_lines=False)
        t.add_column("Card")
        t.add_column("Status")
        for cat in ("suspects", "weapons", "rooms"):
            for c in obs["cards"][cat]:
                if c in you["hand"]:
                    st = "[green]mine[/green]"
                elif c in nb["known_holder"]:
                    st = f"[yellow]held by {nb['known_holder'][c]}[/yellow]"
                elif c in nb["faceup"]:
                    st = "face-up"
                else:
                    st = "?"
                t.add_row(c, st)
        console.print(t)
        if nb["has_one_of"]:
            console.print("Constraints: " + "; ".join(f"{c['player']} has one of {c['cards']}" for c in nb["has_one_of"][-6:]))
        if nb["unrefuted_suggestions"]:
            console.print("[red]Unrefuted:[/red] " + "; ".join(str(c["cards"]) for c in nb["unrefuted_suggestions"]))

    def _pick(self, prompt: str, options: list[str]) -> int:
        for i, o in enumerate(options):
            console.print(f"  [{i}] {o}")
        while True:
            raw = self.input_fn(prompt).strip()
            if raw.isdigit() and int(raw) < len(options):
                return int(raw)
            console.print("[red]Invalid choice[/red]")

    def choose_action(self, observation: dict[str, Any], legal_actions: list[Action]) -> Action:
        obs = observation
        self._show(obs)
        if obs.get("last_error"):
            console.print(f"[red]{obs['last_error']}[/red]")
        options: list[tuple[str, Callable[[], Action]]] = []
        for a in legal_actions:
            if a.type == "suggest":
                continue
            options.append((a.key(), (lambda a=a: a)))  # type: ignore[misc]
        if any(a.type == "suggest" for a in legal_actions):
            options.append(("suggest (choose suspect + weapon)", lambda: self._build(obs, "suggest")))
        if obs["can_accuse"]:
            options.append(("ACCUSE (choose suspect + weapon + room)", lambda: self._build(obs, "accuse")))
        idx = self._pick("Your action #: ", [o[0] for o in options])
        return options[idx][1]()

    def _build(self, obs: dict[str, Any], kind: str) -> Action:
        sus = obs["cards"]["suspects"]
        s = sus[self._pick("Suspect #: ", sus)]
        wps, rms = obs["cards"]["weapons"], obs["cards"]["rooms"]
        w = wps[self._pick("Weapon #: ", list(wps))]
        room = obs["you"]["position"] if kind == "suggest" else rms[self._pick("Room #: ", list(rms))]
        return Action(type=kind, player=self.id, suspect=s, weapon=w, room=room)  # type: ignore[arg-type]

    def choose_card_to_show(self, observation: dict[str, Any], cards_that_can_disprove: list[str]) -> str:
        ps = observation["turn"]["pending_suggestion"]
        console.print(f"[bold]{ps['suggester']} suggested {ps['suspect']} / {ps['weapon']} / {ps['room']}. You must show a card.[/bold]")
        if len(cards_that_can_disprove) == 1:
            console.print(f"Showing {cards_that_can_disprove[0]}")
            return cards_that_can_disprove[0]
        return cards_that_can_disprove[self._pick("Show card #: ", cards_that_can_disprove)]

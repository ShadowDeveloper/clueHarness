"""Pure rules engine: new_game, legal_actions, apply_action, check_winner.

Deterministic given a `random.Random`. No LLM code, no I/O. See RULES_SPEC.md.
"""

from __future__ import annotations

import random

from clue.rules import board as B
from clue.rules.cards import max_players, rooms, suspects, weapons
from clue.rules.state import (
    Action,
    Event,
    GameConfig,
    GameState,
    IllegalAction,
    PlayerState,
    Suggestion,
)


def new_game(config: GameConfig, player_ids: list[str], rng: random.Random) -> GameState:
    """Deal a fresh game. Players are seated in canonical suspect order (Scarlet first)."""
    if len(player_ids) != config.num_players:
        raise ValueError("player_ids length must equal config.num_players")
    if len(set(player_ids)) != len(player_ids):
        raise ValueError("player ids must be unique")
    if not 3 <= config.num_players <= max_players(config.edition):
        raise ValueError(f"{config.edition} edition supports 3..{max_players(config.edition)} players")
    if config.teams:
        flat = [p for t in config.teams for p in t]
        if sorted(flat) != sorted(player_ids) or any(len(t) < 1 for t in config.teams) or len(config.teams) < 2:
            raise ValueError("teams must partition the player ids into at least two teams")
    board = B.board_for(config.edition)
    if config.shuffle_seats:  # E: seat order (suspect token + turn order) drawn from the seed
        player_ids = list(player_ids)
        rng.shuffle(player_ids)
    sus = list(suspects(config.edition))
    wps, rms = weapons(config.edition), rooms(config.edition)
    solution = (rng.choice(sus), rng.choice(wps), rng.choice(rms))
    deck = [c for c in sus + list(wps) + list(rms) if c not in solution]
    rng.shuffle(deck)
    n = len(player_ids)
    faceup: list[str] = []
    if config.deal_remainder == "faceup":
        rem = len(deck) % n
        faceup, deck = deck[:rem], deck[rem:]
    players = [PlayerState(id=pid, seat=i, position=B.sq(*board.starts[i])) for i, pid in enumerate(player_ids)]
    for i, card in enumerate(deck):
        players[i % n].hand.append(card)
    for p in players:
        p.hand.sort()
    tokens = {s: B.sq(*board.starts[i]) for i, s in enumerate(sus)}
    weapon_rooms = list(rms)
    rng.shuffle(weapon_rooms)
    weapon_pos = {w: weapon_rooms[i % len(weapon_rooms)] for i, w in enumerate(wps)}
    return GameState(
        config=config,
        players=players,
        solution=solution,
        faceup=faceup,
        token_positions=tokens,
        weapon_positions=weapon_pos,
    )


def check_winner(state: GameState) -> str | None:
    return state.winner


def _suspect_of(state: GameState, p: PlayerState) -> str:
    return suspects(state.config.edition)[p.seat]


def _occupied(state: GameState) -> frozenset[str]:
    return frozenset(state.token_positions.values())


def legal_actions(state: GameState, player_id: str, include_accusations: bool = True) -> list[Action]:
    """Enumerate every legal action for `player_id` in the current state.

    `include_accusations=False` omits the 324 accusation actions (use `can_accuse`) for speed.
    """
    if state.finished:
        return []
    p = state.player(player_id)
    acts: list[Action] = []
    if state.phase == "disprove":
        if state.disprover_index is None or state.players[state.disprover_index].id != player_id:
            return []
        assert state.pending_suggestion is not None
        s = state.pending_suggestion
        for c in (s.suspect, s.weapon, s.room):
            if c in p.hand:
                acts.append(Action(type="show_card", player=player_id, card=c))
        return acts
    if state.current_player().id != player_id or p.eliminated:
        return []
    ed = state.config.edition
    sus = suspects(ed)
    if state.phase == "move":
        if state.roll is None and not state.has_moved:
            acts.append(Action(type="roll", player=player_id))
            if p.position in B.passages_for(ed):
                acts.append(Action(type="passage", player=player_id))
        elif state.roll is not None and not state.has_moved:
            for dest in sorted(B.reachable(p.position, state.roll, _occupied(state), ed)):
                if dest == p.left_room:
                    continue
                acts.append(Action(type="move", player=player_id, to=dest))
            if not acts:  # boxed in: turn continues without moving
                acts.append(Action(type="end_turn", player=player_id))
        _add_accusations(acts, player_id, sus, include_accusations, ed)
        if state.roll is None and not state.has_moved and p.may_suggest and B.is_room(p.position):
            # moved into a room by a suggestion: may suggest without moving
            _add_suggestions(acts, player_id, p.position, sus, ed)
        return acts
    if state.phase == "suggest":
        if p.may_suggest and B.is_room(p.position):
            _add_suggestions(acts, player_id, p.position, sus, ed)
        _add_accusations(acts, player_id, sus, include_accusations, ed)
        acts.append(Action(type="end_turn", player=player_id))
        return acts
    if state.phase == "accuse":
        _add_accusations(acts, player_id, sus, include_accusations, ed)
        acts.append(Action(type="end_turn", player=player_id))
        return acts
    return acts


def _add_suggestions(acts: list[Action], pid: str, room: str, sus: tuple[str, ...], edition: str = "classic") -> None:
    for s in sus:
        for w in weapons(edition):
            acts.append(Action(type="suggest", player=pid, suspect=s, weapon=w, room=room))


def _add_accusations(acts: list[Action], pid: str, sus: tuple[str, ...], include: bool = True, edition: str = "classic") -> None:
    if not include:
        return
    for s in sus:
        for w in weapons(edition):
            for r in rooms(edition):
                acts.append(Action(type="accuse", player=pid, suspect=s, weapon=w, room=r))


def can_accuse(state: GameState, player_id: str) -> bool:
    """Fast check: may `player_id` accuse right now? (accusation is legal in any of their own phases)."""
    if state.finished or state.phase in ("disprove", "end"):
        return False
    p = state.player(player_id)
    return state.current_player().id == player_id and not p.eliminated


def is_legal(state: GameState, action: Action) -> bool:
    if action.type == "accuse":
        sus = suspects(state.config.edition)
        ed = state.config.edition
        return can_accuse(state, action.player) and action.suspect in sus and action.weapon in weapons(ed) and action.room in rooms(ed) and action.to is None and action.card is None
    return any(a == action for a in legal_actions(state, action.player, include_accusations=False))


def apply_action(state: GameState, action: Action, rng: random.Random) -> tuple[GameState, list[Event]]:
    """Return (new_state, events). Raises IllegalAction. Does not mutate `state`."""
    if not is_legal(state, action):
        raise IllegalAction(f"{action.key()} is not legal for {action.player} in phase {state.phase}")
    st = state.model_copy(deep=True)
    events: list[Event] = []
    t = st.turn_number
    p = st.player(action.player)

    if action.type == "roll":
        dice = [rng.randint(1, 6) for _ in range(st.config.dice)]
        st.roll = sum(dice)
        events.append(Event(type="roll", turn=t, player=p.id, public={"dice": dice, "total": st.roll}))
        if not any(a.type == "move" for a in legal_actions(st, p.id, include_accusations=False)):
            events.append(Event(type="boxed_in", turn=t, player=p.id))
    elif action.type == "move":
        assert action.to is not None
        frm = p.position
        _move_token(st, p, action.to)
        st.has_moved = True
        st.roll = None
        if B.is_room(action.to):
            p.may_suggest = True
            st.phase = "suggest"
        else:
            p.may_suggest = False
            st.phase = "accuse"
        events.append(Event(type="move", turn=t, player=p.id, public={"from": frm, "to": action.to}))
    elif action.type == "passage":
        frm = p.position
        dest = B.passages_for(st.config.edition)[frm]
        _move_token(st, p, dest)
        st.has_moved = True
        p.may_suggest = True
        st.phase = "suggest"
        events.append(Event(type="passage", turn=t, player=p.id, public={"from": frm, "to": dest}))
    elif action.type == "suggest":
        assert action.suspect and action.weapon and action.room
        sug = Suggestion(suggester=p.id, suspect=action.suspect, weapon=action.weapon, room=action.room)
        st.pending_suggestion = sug
        p.may_suggest = False
        st.has_moved = True
        st.roll = None
        # summon suspect token & weapon
        st.token_positions[action.suspect] = action.room
        st.weapon_positions[action.weapon] = action.room
        for q in st.players:
            if q.id != p.id and _suspect_of(st, q) == action.suspect and q.position != action.room:
                q.position = action.room
                q.may_suggest = True  # may suggest there on their next turn without moving
        events.append(
            Event(
                type="suggest",
                turn=t,
                player=p.id,
                public={"suspect": sug.suspect, "weapon": sug.weapon, "room": sug.room},
            )
        )
        _advance_disprover(st, events, start_after=st.index_of(p.id))
    elif action.type == "show_card":
        assert st.pending_suggestion is not None and action.card is not None
        sug = st.pending_suggestion
        involved = sorted(set(st.config.team_of(sug.suggester)) | set(st.config.team_of(p.id)))
        if st.config.private_disproofs:
            # C: the table only learns that *someone* disproved; who did it stays between the two parties
            events.append(
                Event(
                    type="disproved",
                    turn=t,
                    player=None,
                    public={"suggester": sug.suggester},
                    private={"card": action.card, "disprover": p.id},
                    private_to=involved,
                )
            )
        else:
            events.append(
                Event(
                    type="disproved",
                    turn=t,
                    player=p.id,
                    public={"suggester": sug.suggester, "disprover": p.id},
                    private={"card": action.card},
                    private_to=involved,
                )
            )
        st.pending_suggestion = None
        st.disprover_index = None
        st.phase = "accuse"
    elif action.type == "accuse":
        assert action.suspect and action.weapon and action.room
        guess = (action.suspect, action.weapon, action.room)
        correct = guess == tuple(st.solution)
        events.append(
            Event(
                type="accuse",
                turn=t,
                player=p.id,
                public={"suspect": guess[0], "weapon": guess[1], "room": guess[2], "correct": correct},
            )
        )
        if correct:
            st.winner = p.id
            st.finished = True
            st.phase = "end"
            events.append(Event(type="game_over", turn=t, player=p.id, public={"winner": p.id, "team": st.config.team_of(p.id), "solution": list(st.solution)}))
        elif st.config.wrong_accusation == "skip_turns":
            # D: sit out the next N own turns instead of leaving the game (still must disprove)
            p.skip_turns = st.config.accusation_penalty_turns
            events.append(Event(type="penalised", turn=t, player=p.id, public={"skip_turns": p.skip_turns}))
            _end_turn(st, events)
        else:
            p.eliminated = True
            events.append(Event(type="eliminated", turn=t, player=p.id))
            if all(q.eliminated for q in st.players):
                st.finished = True
                st.phase = "end"
                events.append(Event(type="game_over", turn=t, player=None, public={"winner": None, "solution": list(st.solution)}))
            else:
                _end_turn(st, events)
    elif action.type == "end_turn":
        _end_turn(st, events)
    return st, events


def _move_token(st: GameState, p: PlayerState, dest: str) -> None:
    if B.is_room(p.position):
        p.left_room = p.position
    p.position = dest
    st.token_positions[_suspect_of(st, p)] = dest


def _advance_disprover(st: GameState, events: list[Event], start_after: int) -> None:
    """Find the next player clockwise who can disprove; emit cannot_disprove for those who can't."""
    assert st.pending_suggestion is not None
    sug = st.pending_suggestion
    cards = {sug.suspect, sug.weapon, sug.room}
    n = len(st.players)
    team = set(st.config.team_of(sug.suggester))
    for k in range(1, n):
        idx = (start_after + k) % n
        q = st.players[idx]
        if q.id in team:
            continue  # teammates already share their hands
        # C. private disproofs: bystanders must not learn *who* passed or who showed, so the existence of these
        # events is restricted to the suggester's team and the player concerned (the manager filters on private_to).
        hidden = st.config.private_disproofs
        viewers = sorted(team | {q.id}) if hidden else []
        if cards & set(q.hand):
            st.disprover_index = idx
            st.phase = "disprove"
            events.append(Event(type="can_disprove", turn=st.turn_number, player=q.id, public={"suggester": sug.suggester}, private_to=viewers, hidden=hidden))
            return
        events.append(Event(type="cannot_disprove", turn=st.turn_number, player=q.id, public={"suggester": sug.suggester}, private_to=viewers, hidden=hidden))
    events.append(
        Event(
            type="no_one_disproved",
            turn=st.turn_number,
            player=sug.suggester,
            public={"suspect": sug.suspect, "weapon": sug.weapon, "room": sug.room},
        )
    )
    st.pending_suggestion = None
    st.disprover_index = None
    st.phase = "accuse"


def _end_turn(st: GameState, events: list[Event]) -> None:
    cur = st.current_player()
    cur.may_suggest = False
    cur.left_room = None
    st.roll = None
    st.has_moved = False
    st.pending_suggestion = None
    st.disprover_index = None
    st.turn_number += 1
    if st.turn_number >= st.config.max_turns:
        st.finished = True
        st.phase = "end"
        events.append(Event(type="game_over", turn=st.turn_number, player=None, public={"winner": None, "reason": "max_turns", "solution": list(st.solution)}))
        return
    n = len(st.players)
    alive = [q for q in st.players if not q.eliminated]
    max_skip = max((q.skip_turns for q in alive), default=0)
    for k in range(1, n * (max_skip + 1) + 1):  # D: enough laps that every penalty runs out
        idx = (st.current + k) % n
        q = st.players[idx]
        if q.eliminated:
            continue
        if q.skip_turns > 0:  # D: penalised player sits this one out
            q.skip_turns -= 1
            events.append(Event(type="turn_skipped", turn=st.turn_number, player=q.id, public={"remaining": q.skip_turns}))
            st.turn_number += 1
            if st.turn_number >= st.config.max_turns:
                break
            continue
        st.current = idx
        st.phase = "move"
        events.append(Event(type="turn_start", turn=st.turn_number, player=q.id))
        return
    st.finished = True
    st.phase = "end"
    if not any(e.type == "game_over" for e in events):
        reason = "no_active_players" if st.turn_number < st.config.max_turns else "max_turns"
        events.append(Event(type="game_over", turn=st.turn_number, player=None, public={"winner": None, "reason": reason, "solution": list(st.solution)}))

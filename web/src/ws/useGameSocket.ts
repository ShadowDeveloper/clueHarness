import { useEffect, useReducer, useRef } from "react";
import { wsUrl } from "../api/client";
import type { Finished, Frame, GameEvent, GameState, PendingRequest } from "../api/types";

export interface GameView {
  state: GameState | null;
  events: GameEvent[];
  request: PendingRequest | null;
  pendingFor: string | null;
  handoffPending: string | null;
  finished: Finished | null;
  stopped: string | null | false;
  error: string | null;
  connected: boolean;
}

const initial: GameView = { state: null, events: [], request: null, pendingFor: null, handoffPending: null, finished: null, stopped: false, error: null, connected: false };

export function reduce(v: GameView, f: Frame | { type: "_conn"; connected: boolean }): GameView {
  switch (f.type) {
    case "_conn":
      return { ...v, connected: f.connected };
    case "snapshot":
      return { ...v, state: f.state, events: f.events, request: f.request, pendingFor: f.pending_for, handoffPending: f.handoff_pending, finished: f.finished ?? null, error: null };
    case "events": {
      // events carry `seq`; de-duplicate on reconnect and keep order
      const have = new Set(v.events.map((e) => e.seq));
      const add = f.events.filter((e) => !have.has(e.seq));
      const state = v.state ? { ...f.state, candidates: f.state.candidates ?? v.state.candidates, omniscient: f.state.omniscient ? { ...f.state.omniscient, candidates: Object.fromEntries(Object.entries(f.state.omniscient.candidates).map(([k, c]) => [k, c ?? v.state?.omniscient?.candidates[k] ?? null])) } : v.state.omniscient } : f.state;
      return { ...v, state, events: add.length ? [...v.events, ...add] : v.events };
    }
    case "request":
      return { ...v, request: f.request, pendingFor: f.pending_for, handoffPending: f.handoff_pending, state: v.state ? { ...v.state, active_seat: f.active_seat, handoff_pending: f.handoff_pending } : v.state };
    case "control":
      return { ...v, state: v.state ? { ...v.state, paused: f.paused, delay: f.delay } : v.state };
    case "presence":
      return { ...v, state: v.state ? { ...v.state, presence: f.presence, waiting_for: f.waiting_for, started: f.started } : v.state };
    case "finished":
      return { ...v, finished: { summary: f.summary, replays: f.replays, solution: f.solution }, request: null, state: v.state ? { ...v.state, finished: true, winner: f.summary.winner } : v.state };
    case "stopped":
      return { ...v, stopped: f.resumable, request: null };
    case "error":
      return { ...v, error: f.message };
    default:
      return v;
  }
}

/** Live game channel with auto-reconnect; the server re-sends a full snapshot on every connect. */
export function useGameSocket(gameId: string | undefined, token: string | undefined, view?: string): GameView {
  const [v, dispatch] = useReducer(reduce, initial);
  const retry = useRef(0);
  useEffect(() => {
    if (!gameId || !token) return;
    let ws: WebSocket | null = null;
    let closed = false;
    let timer: number | undefined;
    const connect = () => {
      const qs = new URLSearchParams({ k: token, ...(view ? { view } : {}) });
      ws = new WebSocket(wsUrl(`/ws/games/${gameId}?${qs}`));
      ws.onopen = () => { retry.current = 0; dispatch({ type: "_conn", connected: true }); };
      ws.onmessage = (m) => dispatch(JSON.parse(m.data) as Frame);
      ws.onclose = (e) => {
        dispatch({ type: "_conn", connected: false });
        if (closed || e.code === 4403) return;
        timer = window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry.current++));
      };
    };
    connect();
    const ping = window.setInterval(() => ws?.readyState === 1 && ws.send('{"type":"ping"}'), 25000);
    return () => { closed = true; window.clearInterval(ping); window.clearTimeout(timer); ws?.close(); };
  }, [gameId, token, view]);
  return v;
}

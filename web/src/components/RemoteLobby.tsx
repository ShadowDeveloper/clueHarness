import { useState } from "react";
import type { GameState } from "../api/types";

interface Props {
  state: GameState;
  role: "owner" | "spectator" | "seat";
  me: string | null;
  invites: Record<string, string> | null; // host only
  onStart?: () => void;
}

export function inviteUrl(gameId: string, token: string): string {
  return `${location.origin}/game/${gameId}?k=${token}`;
}

/** Remote game waiting room: shows who has joined; the host sees one invite link per human seat. */
export default function RemoteLobby({ state, role, me, invites, onStart }: Props) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (seat: string, url: string) => {
    try { await navigator.clipboard.writeText(url); setCopied(seat); setTimeout(() => setCopied(null), 1500); } catch { /* clipboard blocked: the input is selectable */ }
  };
  const seatRow = (pid: string) => {
    const p = state.board.players.find((q) => q.id === pid);
    const here = (state.presence[pid] ?? 0) > 0;
    return (
      <div key={pid} className="row" style={{ justifyContent: "space-between", gap: 12 }}>
        <span><span className={here ? "ok" : "dim"}>●</span> <b>{pid}</b> <span className="dim">{p?.suspect_token}{p?.name ? ` · ${p.name}` : ""}</span>{pid === me && <span className="pill hot" style={{ marginLeft: 6 }}>you</span>}</span>
        {invites?.[pid] ? (
          <span className="row">
            <input readOnly className="mono" style={{ width: "min(340px, 60vw)", fontSize: 11 }} value={inviteUrl(state.id, invites[pid])} onFocus={(e) => e.currentTarget.select()} />
            <button onClick={() => copy(pid, inviteUrl(state.id, invites[pid]))}>{copied === pid ? "copied ✓" : "copy link"}</button>
          </span>
        ) : <span className="dim">{here ? "joined" : "waiting…"}</span>}
      </div>
    );
  };
  return (
    <div className="curtain remote-lobby" role="dialog" aria-modal="true">
      <h1>Waiting for players</h1>
      <p className="dim">{state.waiting_for.length ? `${state.waiting_for.length} seat${state.waiting_for.length > 1 ? "s" : ""} still to join: ${state.waiting_for.join(", ")}` : "everyone is here"}</p>
      <div className="panel" style={{ display: "grid", gap: 8 }}>
        {state.humans.map(seatRow)}
      </div>
      {role === "owner" && invites && <p className="dim" style={{ fontSize: 12, maxWidth: 560 }}>Send each link to exactly one player — it shows that seat's hand. The game starts when every seat has opened its link. Keep this tab open to watch as the host{me ? "" : " (omniscient links are only offered in bot-only games)"}.</p>}
      {role === "owner" && onStart && state.waiting_for.length > 0 && <button className="primary" onClick={onStart}>Start anyway (missing seats can still join later)</button>}
      {role === "seat" && <p className="dim">Keep this tab open — your hand appears as soon as everyone has joined.</p>}
    </div>
  );
}

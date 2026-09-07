import type { GameState } from "../api/types";

interface Props {
  state: GameState;
  connected: boolean;
  role: "owner" | "spectator" | "seat";
  viewers: string[];
  view: string;
  onView: (v: string) => void;
  onPause?: () => void;
  onDelay?: (d: number) => void;
  onSave?: () => void;
  onQuit?: () => void;
  onCoach?: () => void;
  onInvites?: () => void;
  coachOn?: boolean;
  spend?: number;
}

export default function StatusBar({ state, connected, role, viewers, view, onView, onPause, onDelay, onSave, onQuit, onCoach, onInvites, coachOn, spend }: Props) {
  const t = state.turn;
  const llmCost = Object.values(state.llm).reduce((a, s) => a + (s.cost_usd ?? 0), 0) + (spend ?? 0);
  return (
    <div className="status panel">
      <span className={connected ? "ok" : "bad"} title={connected ? "connected" : "reconnecting…"}>●</span>
      <span>seed <b className="mono">{state.seed}</b></span>
      <span>turn <b>{t.number}</b> · {t.current_player} · <span className="dim">{t.phase}</span>{t.roll ? <> · rolled <b>{t.roll}</b></> : null}</span>
      {state.viewer === "__omni__" && <span className="pill hot">omniscient</span>}
      {state.viewer === "__table__" && <span className="pill">table view</span>}
      {state.remote && role === "seat" && <span className="pill hot">{state.viewer}</span>}
      {state.remote && onInvites && <button onClick={onInvites} title="invite links for the human seats">Invites <kbd>i</kbd></button>}
      {role === "seat" && state.humans.length > 0 && onCoach && !state.finished && <button className={coachOn ? "primary" : ""} onClick={onCoach}>Coach <kbd>h</kbd></button>}
      {state.candidates != null && <span className="pill" title="envelope combinations still possible for this seat">{state.candidates} left</span>}
      {viewers.length > 1 && (
        <label className="row">view <select value={view} onChange={(e) => onView(e.target.value)}>{viewers.map((v) => <option key={v} value={v}>{v === "__omni__" ? "omniscient" : v}</option>)}</select> <kbd>v</kbd></label>
      )}
      {role === "owner" && !state.finished && (
        <>
          <button onClick={onPause} title="pause AI turns">{state.paused ? "▶ Resume" : "⏸ Pause"} <kbd>space</kbd></button>
          <span className="row dim">speed <button onClick={() => onDelay?.(Math.min(5, state.delay + 0.2))}>−</button><span className="mono">{state.delay.toFixed(1)}s</span><button onClick={() => onDelay?.(Math.max(0, state.delay - 0.2))}>+</button></span>
          {state.humans.length > 0 && onCoach && <button className={coachOn ? "primary" : ""} onClick={onCoach}>Coach <kbd>h</kbd></button>}
          <button onClick={onSave}>Save <kbd>ctrl+s</kbd></button>
          <button className="danger" onClick={onQuit}>Quit &amp; save <kbd>q</kbd></button>
        </>
      )}
      {llmCost > 0 && <span className="pill">${llmCost.toFixed(4)}</span>}
      {Object.keys(state.ponder).length > 0 && <span className="pill" title={JSON.stringify(state.ponder)}>ponder</span>}
      {state.error && <span className="bad">{state.error}</span>}
    </div>
  );
}

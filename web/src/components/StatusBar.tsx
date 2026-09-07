import type { GameState } from "../api/types";
import { tokenColor, tokenGlyph } from "./Board";

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
  const you = state.you;
  const where = you ? (/^\d+,\d+$/.test(you.position) ? `at ${you.position}` : `in the ${you.position}`) : null;
  const canControl = role === "owner" && !state.finished;
  return (
    <div className="tstatus">
      <div className="tline">
        <span className={connected ? "ok" : "bad"} title={connected ? "connected" : "reconnecting…"}>●</span>
        {you ? <span>You are <b style={{ color: tokenColor(you.suspect_token) }}>{tokenGlyph(you.suspect_token)} {you.suspect_token}</b> ({you.id}) {where} &nbsp;·&nbsp; your cards: <span className="accent">{you.hand.join(", ")}</span>{state.cards.faceup.length ? <span className="dim"> · face-up: {state.cards.faceup.join(", ")}</span> : null}</span>
          : <span>{state.viewer === "__omni__" ? <span className="pill hot">omniscient</span> : state.viewer === "__table__" ? <span className="pill">table view</span> : <span>viewing {state.viewer}</span>}</span>}
        <span>&nbsp;·&nbsp; turn <b>{t.number}</b> · {t.current_player} · <span className="dim">{t.phase}</span>{t.roll ? <> · rolled <b>{t.roll}</b></> : null}</span>
        {state.candidates != null && <span title="envelope combinations still possible for this seat">&nbsp;·&nbsp; {state.candidates} left</span>}
        <span className="dim" style={{ marginLeft: "auto" }}>seed {state.seed}{llmCost > 0 ? ` · $${llmCost.toFixed(4)}` : ""}{state.paused ? " · PAUSED" : ""} · AI pace {state.delay.toFixed(1)}s{state.error ? <span className="bad"> · {state.error}</span> : null}</span>
      </div>
      <div className="tkeys">
        {canControl && <button onClick={onPause}><kbd>space</kbd> {state.paused ? "Resume" : "Pause"}</button>}
        {canControl && <button onClick={() => onDelay?.(Math.max(0, state.delay - 0.2))}><kbd>+</kbd> Faster</button>}
        {canControl && <button onClick={() => onDelay?.(Math.min(5, state.delay + 0.2))}><kbd>-</kbd> Slower</button>}
        {onCoach && !state.finished && <button className={coachOn ? "on" : ""} onClick={onCoach}><kbd>h</kbd> Coach</button>}
        {viewers.length > 1 && <label><kbd>v</kbd> view <select value={view} onChange={(e) => onView(e.target.value)}>{viewers.map((v) => <option key={v} value={v}>{v === "__omni__" ? "omniscient" : v}</option>)}</select></label>}
        {state.remote && onInvites && <button onClick={onInvites}><kbd>i</kbd> Invites</button>}
        {canControl && <button onClick={onSave}><kbd>ctrl+s</kbd> Save</button>}
        {canControl && <button className="danger" onClick={onQuit}><kbd>q</kbd> Quit &amp; save</button>}
        {Object.keys(state.ponder).length > 0 && <span className="pill" title={JSON.stringify(state.ponder)}>ponder</span>}
      </div>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Action, Board as Geometry, CoachHints } from "../api/types";
import ActionPanel from "../components/ActionPanel";
import Board from "../components/Board";
import EventLog from "../components/EventLog";
import HotseatGate from "../components/HotseatGate";
import Notebook, { Deductions } from "../components/Notebook";
import Omniscient from "../components/Omniscient";
import RemoteLobby from "../components/RemoteLobby";
import StatusBar from "../components/StatusBar";
import { useGameSocket } from "../ws/useGameSocket";
import { loadTokens, saveTokens } from "./Lobby";

export default function Game() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const tokens = loadTokens(id);
  const k = sp.get("k") ?? tokens.owner ?? tokens.seat ?? tokens.spectator ?? "";
  const view = sp.get("view") ?? undefined;
  const v = useGameSocket(id, k || undefined, view);
  // role is only a UI hint (what to show); the server decides what this token may see/do
  const s = v.state;
  const role: "owner" | "spectator" | "seat" = k && k === tokens.owner ? "owner" : k === tokens.spectator && k !== tokens.owner ? "spectator" : s?.remote && s.you && k !== tokens.owner ? "seat" : s?.viewer === "__table__" ? "spectator" : tokens.owner ? "owner" : s?.remote ? "seat" : "owner";
  const [invites, setInvites] = useState<Record<string, string> | null>(null);
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [coach, setCoach] = useState<CoachHints | null>(null);
  const [coachOn, setCoachOn] = useState(false);
  const [showInvites, setShowInvites] = useState(false);
  const [boardPick, setBoardPick] = useState<{ fn: ((t: string) => void) | null; hl: string[] }>({ fn: null, hl: [] });

  useEffect(() => { api.board().then(setGeo); }, []);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 5000); return () => clearTimeout(t); } }, [toast]);

  const me = s?.you?.id ?? null;
  // remember a seat link so the "games on this server" list can reopen it
  useEffect(() => { if (s?.remote && s.you && k && k !== tokens.owner) saveTokens(id, { seat: k }); }, [s?.remote, s?.you?.id, k]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (s?.remote && role === "owner" && !invites) api.invites(id, k).then((r) => setInvites(r.seats)).catch(() => setInvites({})); }, [s?.remote, role, id, k, invites]);
  const viewers = useMemo(() => (s ? (s.humans.length ? (s.hotseat ? s.humans : []) : ["__omni__", ...s.board.players.map((p) => p.id)]) : []), [s]);

  const guard = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setToast(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(false); }
  };
  const submit = useCallback(async (body: { action?: Action; card?: string }) => {
    if (!v.request) return;
    await guard(() => api.act(id, k, { request_id: v.request!.request_id, ...body, player: s?.hotseat || s?.remote ? me ?? undefined : undefined }));
    setCoach(null);
  }, [v.request, id, k, me, s?.hotseat]); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshCoach = useCallback(() => guard(async () => setCoach(await api.coach(id, k, s?.hotseat ? me ?? undefined : undefined))), [id, k, me, s?.hotseat]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (coachOn && v.request?.kind === "action") void refreshCoach(); }, [coachOn, v.request?.request_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const onPause = () => guard(() => api.control(id, k, { pause: !s?.paused }));
  const onDelay = (d: number) => guard(() => api.control(id, k, { delay: d }));
  const onSave = () => guard(async () => { const r = await api.save(id, k); setToast(`saved to ${r.path}`); });
  const onQuit = () => guard(async () => { const r = await api.stop(id, k); setToast(r.path ? `saved to ${r.path} — resume from the lobby` : "stopped"); setTimeout(() => nav("/"), 1500); });
  const cycleView = () => { if (viewers.length < 2) return; const i = viewers.indexOf(view ?? viewers[0]); setSp({ k, view: viewers[(i + 1) % viewers.length] }); };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); onSave(); return; }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === " " && role === "owner") { e.preventDefault(); onPause(); }
      if (e.key === "v") cycleView();
      if (e.key === "h" && me) setCoachOn((c) => !c);
      if (e.key === "q" && role === "owner") onQuit();
      if (e.key === "i" && role === "owner" && s?.remote) setShowInvites((x) => !x);
      if (e.key === "+" || e.key === "=") onDelay(Math.max(0, (s?.delay ?? 0) - 0.2));
      if (e.key === "-") onDelay(Math.min(5, (s?.delay ?? 0) + 0.2));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  if (!k) return <div className="page panel">This game needs its secret link (<span className="mono">?k=…</span>).</div>;
  if (!s || !geo) return <div className="page dim">{v.connected ? "loading…" : "connecting…"}</div>;

  const showGate = s.hotseat && s.handoff_pending && role === "owner" && (view ?? s.humans[0]) === s.handoff_pending;
  const gateSeat = s.handoff_pending;
  const canAct = (role === "owner" || role === "seat") && !!s.you && s.seat_visible;
  const inRemoteLobby = s.remote && !s.started && !s.finished && v.stopped === false;

  return (
    <div className="tui">
      {inRemoteLobby && <RemoteLobby state={s} role={role} me={me} invites={role === "owner" ? invites : null} onStart={role === "owner" ? () => guard(() => api.control(id, k, { start: true })) : undefined} />}
      {!inRemoteLobby && showInvites && s.remote && role === "owner" && (
        <div className="curtain" onClick={() => setShowInvites(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{ display: "grid", gap: 12 }}>
            <RemoteLobbyInline state={s} invites={invites} />
            <button onClick={() => setShowInvites(false)}>close <kbd>i</kbd></button>
          </div>
        </div>
      )}
      {showGate && gateSeat && <HotseatGate seat={gateSeat} onReady={() => guard(() => api.control(id, k, { acknowledge_seat: gateSeat }))} />}
      {s.hotseat && s.handoff_pending && role === "owner" && (view ?? s.humans[0]) !== s.handoff_pending && (
        <div className="curtain"><h1>{s.handoff_pending}'s turn</h1><p className="dim">Pass the device; switch the view to continue.</p><button className="primary" onClick={() => setSp({ k, view: s.handoff_pending! })}>Switch to {s.handoff_pending}</button></div>
      )}
      <div className="col board-col">
        <div className="tpanel" data-title="Hill House — ground floor">
          <Board geo={geo} tokens={s.board.token_positions} weapons={s.board.weapon_positions} players={s.board.players} highlights={boardPick.hl} here={s.you?.position ?? null} you={s.you?.suspect_token ?? null} onPick={boardPick.fn ?? undefined} />
        </div>
      </div>
      <div className="col mid-col">
        <div className="tpanel grow" data-title={s.omniscient ? "All hands (omniscient) — v to view one seat" : s.notebook ? (me ? "Detective notes  ✔ has  ✘ hasn't  ? unknown" : `Notebook of ${s.notebook.viewer}`) : "Notebook"}>
          {s.omniscient ? <Omniscient state={s} /> : s.notebook ? <Notebook state={s} nb={s.notebook} onNote={canAct ? async (n) => { await guard(() => api.note(id, k, n, s.hotseat || s.remote ? me ?? undefined : undefined)); } : undefined} /> : <div className="dim">Table view: no private information.</div>}
        </div>
        {s.notebook && <div className="tpanel" data-title={me ? "Deductions" : `Deductions of ${s.notebook.viewer}`}><Deductions nb={s.notebook} /></div>}
        {coachOn && me && (
          <div className="tpanel coach" data-title="Coach">
            {coach ? <>
              <div><b>{coach.candidates}</b> envelope combination(s) possible{coach.most_likely && <> · most likely {coach.most_likely.suspect} · {coach.most_likely.weapon} · {coach.most_likely.room} ({Math.round(coach.most_likely.p * 100)}%)</>}</div>
              {coach.deductions.map((d, i) => <div key={i} className="ok">✓ {d}</div>)}
              {coach.expert_action && <div className="info">expert would: {coach.expert_action.key}</div>}
              {coach.error && <div className="dim">no recommendation ({coach.error})</div>}
            </> : <span className="dim">hints appear on your turn</span>}
            <div className="dim" style={{ fontSize: 11 }}>uses of coach are logged in the replay</div>
          </div>
        )}
      </div>
      <div className="col right-col">
        <div className="tpanel grow log-panel" data-title={s.viewer === "__omni__" ? "What happened (un-redacted)" : "What happened"}>
          <EventLog events={v.events} me={me} />
        </div>
        <div className="tpanel move" data-title={canAct ? "Your move" : s.finished ? "Game over" : "Waiting — the butler is watching"}>
          {canAct ? <ActionPanel state={s} request={v.request} busy={busy} onSubmit={submit} onPickFromBoard={(fn, hl) => setBoardPick({ fn, hl })} /> : <div className="action"><div className="banner dim">{s.finished ? `Game over — ${s.winner ? `${s.winner} wins` : "no winner"}.` : s.turn.acting ? `${s.turn.acting} is ${s.turn.phase === "disprove" ? "choosing a card to show" : "thinking"}…` : "…"}</div></div>}
          {v.finished && <div className="banner" style={{ marginTop: 6 }}><b>GAME OVER — {v.finished.summary.winner ? (v.finished.summary.winner === me ? "You win! 🎉" : `${v.finished.summary.winner} wins.`) : "Nobody solved it."}</b><br />Solution: {v.finished.solution.join(" · ")} <span className="dim">· {v.finished.summary.turns} turns · replays: {v.finished.replays.map((r) => r.split("/").pop()).join(", ")}</span></div>}
          {v.stopped !== false && <div className="banner warn" style={{ marginTop: 6 }}>Game stopped{v.stopped ? ` — checkpoint ${v.stopped}` : ""}. Resume from the lobby.</div>}
        </div>
      </div>
      <StatusBar state={s} connected={v.connected} role={role} viewers={viewers} onInvites={s.remote && role === "owner" ? () => setShowInvites((x) => !x) : undefined} view={view ?? viewers[0] ?? s.viewer} onView={(vw) => setSp({ k, view: vw })} onPause={onPause} onDelay={onDelay} onSave={onSave} onQuit={onQuit} onCoach={me ? () => setCoachOn((c) => !c) : undefined} coachOn={coachOn} />
      {toast && <div className="toast" role="alert">{toast}</div>}
    </div>
  );
}

/** Invite links re-shown mid-game (host presses `i`). */
function RemoteLobbyInline({ state, invites }: { state: import("../api/types").GameState; invites: Record<string, string> | null }) {
  return (
    <div className="panel" style={{ minWidth: 520, display: "grid", gap: 8 }}>
      <h3>Invite links</h3>
      {state.humans.map((pid) => (
        <div key={pid} className="row" style={{ justifyContent: "space-between" }}>
          <span><span className={(state.presence[pid] ?? 0) > 0 ? "ok" : "dim"}>●</span> <b>{pid}</b></span>
          {invites?.[pid] ? <input readOnly className="mono" style={{ width: 360, fontSize: 11 }} value={`${location.origin}/game/${state.id}?k=${invites[pid]}`} onFocus={(e) => e.currentTarget.select()} /> : <span className="dim">—</span>}
        </div>
      ))}
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Action, Board as Geometry, CoachHints } from "../api/types";
import ActionPanel from "../components/ActionPanel";
import Board from "../components/Board";
import EventLog from "../components/EventLog";
import HotseatGate from "../components/HotseatGate";
import Notebook from "../components/Notebook";
import Omniscient from "../components/Omniscient";
import StatusBar from "../components/StatusBar";
import { useGameSocket } from "../ws/useGameSocket";
import { loadTokens } from "./Lobby";

export default function Game() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const k = sp.get("k") ?? loadTokens(id).owner ?? loadTokens(id).spectator ?? "";
  const view = sp.get("view") ?? undefined;
  const tokens = loadTokens(id);
  const role: "owner" | "spectator" = k && k === tokens.spectator && k !== tokens.owner ? "spectator" : "owner";
  const v = useGameSocket(id, k || undefined, view);
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [coach, setCoach] = useState<CoachHints | null>(null);
  const [coachOn, setCoachOn] = useState(false);
  const [boardPick, setBoardPick] = useState<{ fn: ((t: string) => void) | null; hl: string[] }>({ fn: null, hl: [] });

  useEffect(() => { api.board().then(setGeo); }, []);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 5000); return () => clearTimeout(t); } }, [toast]);

  const s = v.state;
  const me = s?.you?.id ?? null;
  const viewers = useMemo(() => (s ? (s.humans.length ? (s.hotseat ? s.humans : []) : ["__omni__", ...s.board.players.map((p) => p.id)]) : []), [s]);

  const guard = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setToast(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(false); }
  };
  const submit = useCallback(async (body: { action?: Action; card?: string }) => {
    if (!v.request) return;
    await guard(() => api.act(id, k, { request_id: v.request!.request_id, ...body, player: s?.hotseat ? me ?? undefined : undefined }));
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
  const canAct = role === "owner" && !!s.you && s.seat_visible;

  return (
    <div className="page game-layout">
      {showGate && gateSeat && <HotseatGate seat={gateSeat} onReady={() => guard(() => api.control(id, k, { acknowledge_seat: gateSeat }))} />}
      {s.hotseat && s.handoff_pending && role === "owner" && (view ?? s.humans[0]) !== s.handoff_pending && (
        <div className="curtain"><h1>{s.handoff_pending}'s turn</h1><p className="dim">Pass the device; switch the view to continue.</p><button className="primary" onClick={() => setSp({ k, view: s.handoff_pending! })}>Switch to {s.handoff_pending}</button></div>
      )}
      <div className="board panel">
        <Board geo={geo} tokens={s.board.token_positions} weapons={s.board.weapon_positions} players={s.board.players} highlights={boardPick.hl} here={s.you?.position ?? null} onPick={boardPick.fn ?? undefined} />
        <div className="row" style={{ marginTop: 8, fontSize: 12 }}>
          {s.board.players.map((p) => <span key={p.id} className="pill" style={{ borderColor: p.id === s.turn.current_player ? "var(--accent)" : undefined, opacity: p.eliminated ? 0.5 : 1 }}>{p.id} {p.suspect_token} <span className="dim">{p.label}{p.name ? ` · ${p.name}` : ""} · {p.hand_size} cards</span>{p.eliminated ? " ✗" : ""}</span>)}
        </div>
        {s.you && <div className="row" style={{ marginTop: 8 }}><span className="dim">Your hand:</span>{s.you.hand.map((c) => <span key={c} className="pill ok">{c}</span>)}{s.cards.faceup.length > 0 && <span className="dim">face-up: {s.cards.faceup.join(", ")}</span>}</div>}
        {v.finished && <div className="panel" style={{ marginTop: 8, borderColor: "var(--accent)" }}><b>Game over.</b> {v.finished.summary.winner ? `${v.finished.summary.winner} wins` : "No winner"} after {v.finished.summary.turns} turns. Solution: <b>{v.finished.solution.join(" · ")}</b>. Replays: {v.finished.replays.map((r) => <span key={r} className="mono dim"> {r.split("/").pop()}</span>)}</div>}
        {v.stopped !== false && <div className="panel warn" style={{ marginTop: 8 }}>Game stopped{v.stopped ? ` — checkpoint ${v.stopped}` : ""}. Resume from the lobby.</div>}
      </div>
      <div className="right">
        <StatusBar state={s} connected={v.connected} role={role} viewers={viewers} view={view ?? viewers[0] ?? s.viewer} onView={(vw) => setSp({ k, view: vw })} onPause={onPause} onDelay={onDelay} onSave={onSave} onQuit={onQuit} onCoach={me ? () => setCoachOn((c) => !c) : undefined} coachOn={coachOn} />
        {canAct ? <ActionPanel state={s} request={v.request} busy={busy} onSubmit={submit} onPickFromBoard={(fn, hl) => setBoardPick({ fn, hl })} /> : <div className="action panel"><div className="banner dim">{s.finished ? `Game over — ${s.winner ? `${s.winner} wins` : "no winner"}.` : s.turn.acting ? `${s.turn.acting} is ${s.turn.phase === "disprove" ? "choosing a card to show" : "thinking"}…` : "…"}</div></div>}
        {coachOn && me && (
          <div className="coach">
            <b>Coach</b> {coach ? <>· <b>{coach.candidates}</b> envelope combination(s) possible{coach.most_likely && <> · most likely {coach.most_likely.suspect} · {coach.most_likely.weapon} · {coach.most_likely.room} ({Math.round(coach.most_likely.p * 100)}%)</>}
              {coach.deductions.map((d, i) => <div key={i} className="ok">✓ {d}</div>)}
              {coach.expert_action && <div className="info">expert would: {coach.expert_action.key}</div>}
              {coach.error && <div className="dim">no recommendation ({coach.error})</div>}
            </> : <span className="dim">· hints appear on your turn</span>}
            <span className="dim"> — uses of coach are logged in the replay</span>
          </div>
        )}
        <div className="panel" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <h3>Log{s.viewer === "__omni__" ? " (un-redacted)" : me ? ` (as ${me})` : ""}</h3>
          <EventLog events={v.events} me={me} />
        </div>
        <div className="panel" style={{ maxHeight: 420, overflow: "auto" }}>
          <h3>{s.omniscient ? "All hands (omniscient)" : s.notebook ? `Notebook — ${s.notebook.viewer}` : "Notebook"}</h3>
          {s.omniscient ? <Omniscient state={s} /> : s.notebook ? <Notebook state={s} nb={s.notebook} onNote={canAct ? async (n) => { await guard(() => api.note(id, k, n, s.hotseat ? me ?? undefined : undefined)); } : undefined} /> : <div className="dim">Table view: no private information.</div>}
        </div>
      </div>
      {toast && <div className="toast" role="alert">{toast}</div>}
    </div>
  );
}

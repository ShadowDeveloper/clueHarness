import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Catalog, GameListItem, PlayerSpec } from "../api/types";

const DEFAULT: PlayerSpec[] = [
  { id: "P1", kind: "human" },
  { id: "P2", kind: "baseline", bot: "expert" },
  { id: "P3", kind: "baseline", bot: "heuristic" },
  { id: "P4", kind: "llm", strategy: "bayesian_probabilist", prompt_profile: "compact" },
];

export interface Tokens { owner?: string; spectator?: string; seats?: Record<string, string>; seat?: string }
export function saveTokens(id: string, t: Tokens) {
  localStorage.setItem(`clue:${id}`, JSON.stringify({ ...loadTokens(id), ...t }));
}
export function loadTokens(id: string): Tokens {
  try { return JSON.parse(localStorage.getItem(`clue:${id}`) ?? "{}"); } catch { return {}; }
}

export default function Lobby() {
  const nav = useNavigate();
  const [cat, setCat] = useState<Catalog | null>(null);
  const [seats, setSeats] = useState<PlayerSpec[]>(DEFAULT);
  const [seed, setSeed] = useState<string>("");
  const [dice, setDice] = useState(2);
  const [uneven, setUneven] = useState<string>("");
  const [ponder, setPonder] = useState(false);
  const [delay, setDelay] = useState(0.6);
  const [provider, setProvider] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [remote, setRemote] = useState(false);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [saves, setSaves] = useState<{ name: string; seed: number; turn: number; labels: string[] }[]>([]);

  useEffect(() => {
    api.catalog().then((c) => { setCat(c); setProvider(c.default_provider); setUneven(String(c.config_defaults.uneven_deal ?? "")); }).catch((e) => setErr(String(e)));
    api.listGames().then(setGames).catch(() => undefined);
    api.listSaves().then(setSaves).catch(() => undefined);
  }, []);

  const update = (i: number, patch: Partial<PlayerSpec>) => setSeats(seats.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const humans = seats.filter((s) => s.kind === "human").length;

  const start = async (resume?: string) => {
    setBusy(true); setErr(null);
    try {
      const cfg: Record<string, unknown> = { num_players: seats.length, dice };
      if (uneven) cfg.uneven_deal = uneven;
      const wantRemote = remote || (humans > 1 && !cat?.hotseat);
      const g = await api.createGame(resume ? { resume, delay } : { players: seats.map((s, i) => ({ ...s, id: `P${i + 1}` })), seed: seed === "" ? null : Number(seed), config: cfg, ponder, delay, provider: provider || null, remote: wantRemote });
      saveTokens(g.id, { owner: g.owner_token, spectator: g.spectator_token, seats: g.seat_tokens });
      nav(`/game/${g.id}?k=${g.owner_token}`);
    } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <div className="page grid" style={{ gridTemplateColumns: "minmax(520px, 2fr) 1fr" }}>
      <div className="panel">
        <h3>New game</h3>
        {cat && seats.map((s, i) => (
          <div className="lobby-seat" key={i} style={{ marginBottom: 6 }}>
            <span className="mono dim">P{i + 1}</span>
            <select value={s.kind} onChange={(e) => update(i, { kind: e.target.value as PlayerSpec["kind"], bot: e.target.value === "baseline" ? "expert" : null, strategy: e.target.value === "llm" ? cat.strategies[0] : null })}>{cat.kinds.map((k) => <option key={k}>{k}</option>)}</select>
            {s.kind === "baseline" && <select value={s.bot ?? "heuristic"} onChange={(e) => update(i, { bot: e.target.value })}>{cat.bots.map((b) => <option key={b}>{b}</option>)}</select>}
            {s.kind === "llm" && <select value={s.strategy ?? ""} onChange={(e) => update(i, { strategy: e.target.value })}>{cat.strategies.map((b) => <option key={b}>{b}</option>)}</select>}
            {s.kind === "llm" && <select value={s.tool_mode ?? "precomputed"} onChange={(e) => update(i, { tool_mode: e.target.value, tools: e.target.value !== "none" })}>{cat.tool_modes.map((b) => <option key={b}>{b}</option>)}</select>}
            {s.kind === "llm" && <input list="models" placeholder={cat.default_model} value={s.model ?? ""} onChange={(e) => update(i, { model: e.target.value || null })} />}
            {s.kind === "human" && <input placeholder="name (optional)" value={s.name ?? ""} onChange={(e) => update(i, { name: e.target.value || null })} />}
            {s.kind !== "llm" && <span />}{s.kind === "human" && <span />}{s.kind === "baseline" && <span />}
            <button title="remove" disabled={seats.length <= 3} onClick={() => setSeats(seats.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <datalist id="models">{cat?.known_models.map((m) => <option key={m} value={m} />)}</datalist>
        <div className="row" style={{ marginTop: 6 }}>
          <button disabled={seats.length >= 6} onClick={() => setSeats([...seats, { id: `P${seats.length + 1}`, kind: "baseline", bot: "heuristic" }])}>+ seat</button>
          {humans > 1 && cat && (cat.remote || cat.hotseat) && (
            <label className="row" title="each human gets their own invite link and plays from their own browser">
              <select value={remote || !cat.hotseat ? "remote" : "hotseat"} onChange={(e) => setRemote(e.target.value === "remote")}>
                {cat.hotseat && <option value="hotseat">hot-seat: {humans} humans share this browser</option>}
                {cat.remote && <option value="remote">remote: one invite link per human</option>}
              </select>
            </label>
          )}
          {humans === 1 && cat?.remote && <label className="row dim" style={{ fontSize: 12 }}><input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} /> play from another device (invite link)</label>}
          {humans > 1 && cat && !cat.remote && !cat.hotseat && <span className="warn">several human seats need the server started with <span className="mono">--hotseat</span> or remote seats enabled</span>}
        </div>
        <hr style={{ borderColor: "var(--border)", margin: "12px 0" }} />
        <div className="row">
          <label>seed <input value={seed} onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ""))} placeholder="random" style={{ width: 90 }} /></label>
          <label>dice <select value={dice} onChange={(e) => setDice(Number(e.target.value))}><option value={1}>1d6</option><option value={2}>2d6</option></select></label>
          <label>uneven deal <select value={uneven} onChange={(e) => setUneven(e.target.value)}><option value="">default</option><option value="deal_all">deal all</option><option value="faceup">face-up remainder</option></select></label>
          <label>AI pace <input type="number" min={0} max={5} step={0.1} value={delay} onChange={(e) => setDelay(Number(e.target.value))} style={{ width: 70 }} /> s</label>
          <label><input type="checkbox" checked={ponder} onChange={(e) => setPonder(e.target.checked)} /> ponder</label>
          <label>provider <select value={provider} onChange={(e) => setProvider(e.target.value)}>{cat?.providers.map((p) => <option key={p}>{p}</option>)}</select></label>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button className="primary" disabled={busy || !cat} onClick={() => start()}>{humans ? "Play" : "Spectate"}</button>
          {err && <span className="bad">{err}</span>}
        </div>
        <p className="dim" style={{ fontSize: 12 }}>LLM seats use the server's provider/keys (<span className="mono">.env</span>); <span className="mono">mock</span> is offline. Games autosave to <span className="mono">saves/</span> after every action.</p>
      </div>
      <div className="grid">
        <div className="panel">
          <h3>Resume a saved game</h3>
          {saves.length === 0 && <div className="dim">no checkpoints</div>}
          {saves.map((s) => <div className="row" key={s.name} style={{ justifyContent: "space-between" }}><span><span className="mono">{s.name}</span> <span className="dim">turn {s.turn} · {s.labels.join(", ")}</span></span><button onClick={() => start(s.name)}>Resume</button></div>)}
        </div>
        <div className="panel">
          <h3>Games on this server</h3>
          {games.length === 0 && <div className="dim">none yet</div>}
          {games.map((g) => {
            const t = loadTokens(g.id);
            const mine = t.owner ?? t.seat ?? t.spectator;
            return <div className="row" key={g.id} style={{ justifyContent: "space-between" }}><span><span className="mono">{g.id}</span> <span className="dim">seed {g.seed} · turn {g.turn} · {Object.values(g.labels).join(", ")}{g.finished ? ` · winner ${g.winner ?? "—"}` : ""}{g.remote ? ` · remote${g.waiting_for.length ? ` · waiting for ${g.waiting_for.join(", ")}` : ""}` : ""}</span></span>{mine ? <a href={`/game/${g.id}?k=${mine}`}>open</a> : <span className="dim">need link</span>}</div>;
          })}
        </div>
      </div>
    </div>
  );
}

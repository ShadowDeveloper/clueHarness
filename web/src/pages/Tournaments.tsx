import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, wsUrl } from "../api/client";
import type { TournamentFrame, TournamentStatus } from "../api/types";
import Curves from "../components/Curves";

export default function Tournaments() {
  const nav = useNavigate();
  const { id } = useParams();
  const [list, setList] = useState<Omit<TournamentStatus, "report">[]>([]);
  const [players, setPlayers] = useState("baseline:expert,baseline,baseline,llm:bayesian_probabilist");
  const [games, setGames] = useState(20);
  const [seed, setSeed] = useState(0);
  const [workers, setWorkers] = useState(0);
  const [ponder, setPonder] = useState(false);
  const [maxUsd, setMaxUsd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const refresh = () => api.listTournaments().then(setList).catch(() => undefined);
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  const start = async () => {
    setErr(null);
    try { const t = await api.createTournament({ players_arg: players, games, seed, workers, ponder, max_usd: maxUsd ? Number(maxUsd) : null }); nav(`/tournaments/${t.id}`); refresh(); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };
  return (
    <div className="page grid tourn-grid">
      <div className="grid" style={{ alignContent: "start" }}>
        <div className="panel">
          <h3>New tournament</h3>
          <label>players (CLI shorthand)<input value={players} onChange={(e) => setPlayers(e.target.value)} style={{ width: "100%" }} /></label>
          <div className="row" style={{ marginTop: 6 }}>
            <label>games <input type="number" min={1} max={10000} value={games} onChange={(e) => setGames(Number(e.target.value))} style={{ width: 80 }} /></label>
            <label>seed <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} style={{ width: 80 }} /></label>
            <label title="0 = all CPU cores">workers <input type="number" min={0} max={64} value={workers} onChange={(e) => setWorkers(Number(e.target.value))} style={{ width: 60 }} /></label>
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <label><input type="checkbox" checked={ponder} onChange={(e) => setPonder(e.target.checked)} /> ponder</label>
            <label>max $ <input value={maxUsd} onChange={(e) => setMaxUsd(e.target.value)} placeholder="∞" style={{ width: 70 }} /></label>
            <button className="primary" onClick={start}>Start</button>
          </div>
          {err && <div className="bad">{err}</div>}
        </div>
        <div className="panel">
          <h3>Tournaments</h3>
          {list.length === 0 && <div className="dim">none yet</div>}
          {list.map((t) => <div key={t.id} className="row" style={{ justifyContent: "space-between" }}><a href={`/tournaments/${t.id}`} onClick={(e) => { e.preventDefault(); nav(`/tournaments/${t.id}`); }} className={t.id === id ? "accent" : ""}><span className="mono">{t.id}</span></a><span className="dim">{t.done}/{t.games} · {t.status}</span></div>)}
        </div>
      </div>
      {id ? <Detail id={id} /> : <div className="panel dim">Pick or start a tournament.</div>}
    </div>
  );
}

function Detail({ id }: { id: string }) {
  const [t, setT] = useState<TournamentStatus | null>(null);
  const [log, setLog] = useState<string[]>([]);
  useEffect(() => {
    setT(null); setLog([]);
    api.tournament(id).then(setT).catch(() => undefined);
    const ws = new WebSocket(wsUrl(`/ws/tournaments/${id}`));
    let refreshTimer: number | undefined;
    ws.onmessage = (m) => {
      const f = JSON.parse(m.data) as TournamentFrame;
      if (f.type === "snapshot" || f.type === "done") setT(f);
      else if (f.type === "progress") {
        setLog((l) => [...l.slice(-199), `game ${f.done}/${f.games} seed=${f.seed} winner=${f.winner_label ?? "—"} turns=${f.turns}`]);
        window.clearTimeout(refreshTimer);
        refreshTimer = window.setTimeout(() => api.tournament(id).then(setT).catch(() => undefined), 400); // throttle table refresh
      }
    };
    return () => { ws.close(); window.clearTimeout(refreshTimer); };
  }, [id]);
  if (!t) return <div className="panel dim">loading…</div>;
  const rep = t.report;
  const pct = Math.round((100 * t.done) / t.games);
  return (
    <div className="grid" style={{ alignContent: "start" }}>
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span><b className="mono">{t.id}</b> · {t.players.join(" vs ")} · seed {t.seed} · <span className={t.status === "running" ? "accent" : t.status === "finished" ? "ok" : "warn"}>{t.status}</span>{t.error && <span className="dim"> ({t.error})</span>}</span>
          <span className="row">
            {t.status === "running" && <button className="danger" onClick={() => api.cancelTournament(id)}>Cancel</button>}
            {rep && <><a href={`/api/tournaments/${id}/report.csv`}>csv</a><a href={`/api/tournaments/${id}/report.json`}>json</a><a href={`/api/tournaments/${id}/report.md`}>md</a></>}
          </span>
        </div>
        <div className="progress" style={{ marginTop: 8 }}><div style={{ width: `${pct}%` }} /></div>
        <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>{t.done}/{t.games} games{t.cost.usd ? ` · spend $${Number(t.cost.usd).toFixed(4)}` : ""}</div>
      </div>
      {rep && (
        <div className="panel">
          <h3>Results</h3>
          <table className="tbl">
            <thead><tr><th>agent</th><th>games</th><th>wins</th><th>win rate</th><th>95% CI</th><th>false acc.</th><th>avg turns to win</th><th>illegal</th><th>ELO</th></tr></thead>
            <tbody>{rep.table.map((r) => <tr key={r.agent}><td>{r.agent}</td><td>{r.games}</td><td>{r.wins}</td><td><b>{(r.win_rate * 100).toFixed(0)}%</b></td><td className="dim">{r.win_ci95 ? `${(r.win_ci95[0] * 100).toFixed(0)}–${(r.win_ci95[1] * 100).toFixed(0)}%` : "—"}</td><td>{r.false_accusation_rate ?? "—"}</td><td>{r.avg_turns_to_win ?? "—"}</td><td className={r.illegal_attempts ? "bad" : ""}>{r.illegal_attempts ?? 0}</td><td>{r.elo ?? "—"}</td></tr>)}</tbody>
          </table>
        </div>
      )}
      {rep && Object.keys(rep.curves).length > 0 && <div className="panel"><h3>Candidate curves</h3><Curves curves={rep.curves} /></div>}
      <div className="panel"><h3>Progress</h3><div className="log mono" style={{ maxHeight: 200, fontSize: 12 }}>{log.map((l, i) => <div key={i} className="line">{l}</div>)}{!log.length && <span className="dim">waiting for games…</span>}</div></div>
    </div>
  );
}

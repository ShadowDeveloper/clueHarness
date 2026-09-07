import type { GameState } from "../api/types";

/** Spectator table: true holder of every card + what each seat has deduced (mirrors the TUI OmniscientView). */
export default function Omniscient({ state }: { state: GameState }) {
  const o = state.omniscient;
  if (!o) return null;
  const players = state.board.players.map((p) => p.id);
  const cls = (v: string) => (v === "mine" ? "mine" : v === "env!" ? "env" : v.startsWith("?") ? "q" : "held");
  return (
    <div>
      <div className="row" style={{ marginBottom: 6, fontSize: 13 }}>
        <span className="pill hot">Envelope: {o.solution.join(" · ")}</span>
        {players.map((p) => <span key={p} className="pill">{p}: {o.candidates[p] ?? "…"} left</span>)}
      </div>
      <table className="nb">
        <thead><tr><th>Card</th><th>Truth</th>{players.map((p) => <th key={p}>{p} knows</th>)}</tr></thead>
        <tbody>
          {o.rows.map((r) => (
            <tr key={r.card}>
              <td>{r.card}</td>
              <td className={r.truth === "ENVELOPE" ? "env" : "truth"}>{r.truth}</td>
              {players.map((p) => <td key={p} className={cls(r.knows[p])}>{r.knows[p]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

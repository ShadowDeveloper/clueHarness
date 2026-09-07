import { useState } from "react";
import type { GameState, Notebook as NB } from "../api/types";

interface Props { state: GameState; nb: NB; onNote?: (note: string) => Promise<void>; }

/** Cards × players matrix derived from the viewer's notebook (same marks as the TUI). */
export default function Notebook({ state, nb, onNote }: Props) {
  const players = state.board.players.map((p) => p.id);
  const [note, setNote] = useState("");
  const cell = (card: string, p: string) => {
    if (nb.my_hand.includes(card)) return p === nb.viewer ? ["mine", "✓"] : ["no", "✗"];
    if (nb.faceup.includes(card)) return ["q", "—"];
    const holder = nb.known_holder[card];
    if (holder) return holder === p ? ["held", "✓"] : ["no", "✗"];
    if ((nb.not_held[p] ?? []).includes(card)) return ["no", "✗"];
    const maybe = nb.has_one_of.some((c) => c.player === p && c.cards.includes(card));
    return ["q", maybe ? "?" : ""];
  };
  const envelope = (card: string) => !nb.my_hand.includes(card) && !nb.faceup.includes(card) && !nb.known_holder[card] && players.every((p) => p === nb.viewer || (nb.not_held[p] ?? []).includes(card));
  const cats: [string, string[]][] = [["Suspects", state.cards.suspects], ["Weapons", state.cards.weapons], ["Rooms", state.cards.rooms]];
  return (
    <div>
      <table className="nb">
        <thead><tr><th>Card</th>{players.map((p) => <th key={p} title={state.board.players.find((q) => q.id === p)?.label}>{p}{p === nb.viewer ? " (you)" : ""}</th>)}<th>Env</th></tr></thead>
        <tbody>
          {cats.map(([name, cards]) => (
            <FragmentRows key={name} name={name} cards={cards} players={players} cell={cell} envelope={envelope} />
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8 }}>
        {nb.notes.length > 0 && <ul className="dim" style={{ margin: "4px 0 6px", paddingLeft: 18, fontSize: 12 }}>{nb.notes.slice(-5).map((n, i) => <li key={i}>{n}</li>)}</ul>}
        {onNote && (
          <form className="row" onSubmit={async (e) => { e.preventDefault(); if (note.trim()) { await onNote(note.trim()); setNote(""); } }}>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="add a private note…" style={{ flex: 1 }} maxLength={500} />
            <button type="submit" disabled={!note.trim()}>Note</button>
          </form>
        )}
      </div>
    </div>
  );
}

function FragmentRows({ name, cards, players, cell, envelope }: { name: string; cards: string[]; players: string[]; cell: (c: string, p: string) => string[]; envelope: (c: string) => boolean }) {
  return (
    <>
      <tr className="cat"><td colSpan={players.length + 2}>{name}</td></tr>
      {cards.map((c) => (
        <tr key={c}>
          <td>{c}</td>
          {players.map((p) => { const [cls, txt] = cell(c, p); return <td key={p} className={cls}>{txt}</td>; })}
          <td className={envelope(c) ? "env" : "q"}>{envelope(c) ? "!" : ""}</td>
        </tr>
      ))}
    </>
  );
}

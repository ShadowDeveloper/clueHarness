import { useState } from "react";
import type { GameState, Notebook as NB } from "../api/types";

interface Props { state: GameState; nb: NB; onNote?: (note: string) => Promise<void>; }

/** Cards × players matrix derived from the viewer's notebook (same marks as the TUI). */
export default function Notebook({ state, nb, onNote }: Props) {
  const players = state.board.players.map((p) => p.id);
  const [note, setNote] = useState("");
  // same marks as the TUI NotebookView: ✔ holder, · someone else holds it, ✘ known not to hold, ? unknown
  const holderOf = (card: string) => (nb.my_hand.includes(card) ? nb.viewer : nb.known_holder[card]);
  const cell = (card: string, p: string) => {
    const holder = holderOf(card);
    if (holder === p) return ["mine", "✔"];
    if (holder) return ["q", "·"];
    if ((nb.not_held[p] ?? []).includes(card)) return ["no", "✘"];
    return ["q", "?"];
  };
  const envelope = (card: string) => !nb.my_hand.includes(card) && !nb.faceup.includes(card) && !nb.known_holder[card] && players.every((p) => p === nb.viewer || (nb.not_held[p] ?? []).includes(card));
  const status = (card: string) => {
    if (nb.my_hand.includes(card)) return ["mine", "yours"];
    const h = nb.known_holder[card];
    if (h) return ["held", `${h} has it`];
    if (nb.faceup.includes(card)) return ["q", "face-up"];
    if (envelope(card)) return ["env", "ENVELOPE!"];
    return ["q", ""];
  };
  const cats: [string, string[]][] = [["Suspects", state.cards.suspects], ["Weapons", state.cards.weapons], ["Rooms", state.cards.rooms]];
  return (
    <div>
      <table className="nb">
        <thead><tr><th>Card</th>{players.map((p) => <th key={p} title={state.board.players.find((q) => q.id === p)?.label}>{p}</th>)}<th /></tr></thead>
        <tbody>
          {cats.map(([name, cards]) => (
            <FragmentRows key={name} name={name} cards={cards} players={players} cell={cell} status={status} />
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8 }}>
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

function FragmentRows({ name, cards, players, cell, status }: { name: string; cards: string[]; players: string[]; cell: (c: string, p: string) => string[]; status: (c: string) => string[] }) {
  return (
    <>
      <tr className="cat"><td colSpan={players.length + 2}>{name}</td></tr>
      {cards.map((c) => {
        const [scls, stxt] = status(c);
        return (
          <tr key={c}>
            <td>{c}</td>
            {players.map((p) => { const [cls, txt] = cell(c, p); return <td key={p} className={cls}>{txt}</td>; })}
            <td className={`st ${scls}`}>{stxt}</td>
          </tr>
        );
      })}
    </>
  );
}

/** "Deductions" box under the notebook, same content as the TUI facts panel. */
export function Deductions({ nb }: { nb: NB }) {
  const one = (nb.has_one_of ?? []).slice(-4);
  const unref = ((nb.unrefuted_suggestions as { player: string; cards: string[] }[] | undefined) ?? []).slice(-3);
  const notes = nb.notes.slice(-2);
  if (!one.length && !unref.length && !notes.length) return <div className="dim">Nothing deduced yet. Make suggestions to learn who holds what.</div>;
  return (
    <div className="facts">
      {one.map((c, i) => <div key={`o${i}`}>• {c.player} holds at least one of {c.cards.join(", ")}</div>)}
      {unref.map((c, i) => <div key={`u${i}`}>• <span className="accent">nobody could disprove</span> {c.cards.join(", ")} (suggested by {c.player})</div>)}
      {notes.map((n, i) => <div key={`n${i}`}>• <span className="dim">note:</span> {n}</div>)}
    </div>
  );
}

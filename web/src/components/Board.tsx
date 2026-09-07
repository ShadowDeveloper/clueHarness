import type React from "react";
import { useMemo } from "react";
import type { Board as Geometry, SeatInfo } from "../api/types";

/** Character-grid board that mirrors clue/tui/board_render.py: dots for corridor, ▢ doors, ░ cellar, shaded rooms
 *  with their name on the middle row, weapons as lowercase initials bottom-left, coloured token glyphs, ◆ reachable. */

const TOKEN_LETTER: Record<string, string> = { "Miss Scarlet": "S", "Col. Mustard": "M", "Mrs. White": "W", "Dr. Orchid": "W", "Mr. Green": "G", "Mrs. Peacock": "K", "Prof. Plum": "P" };
export const TOKEN_GLYPH: Record<string, string> = { S: "♛", M: "★", W: "✚", G: "♣", K: "❋", P: "✎" };
const TOKEN_COLOR: Record<string, string> = { S: "var(--S)", M: "var(--M)", W: "var(--W)", G: "var(--G)", K: "var(--K)", P: "var(--P)" };
const SHORT: Record<string, string> = { "Dining Room": "DINING", "Billiard Room": "BILLIARD", Conservatory: "CONSERV.", Kitchen: "KITCHEN", Ballroom: "BALLROOM", Lounge: "LOUNGE", Hall: "HALL", Study: "STUDY", Library: "LIBRARY" };

export function tokenLetter(suspect: string): string { return TOKEN_LETTER[suspect] ?? suspect[0]; }
export function tokenGlyph(suspect: string): string { return TOKEN_GLYPH[tokenLetter(suspect)] ?? tokenLetter(suspect); }
export function tokenColor(suspect: string): string { return TOKEN_COLOR[tokenLetter(suspect)] ?? "#ccc"; }

/** "r,c" corridor square or a room name. */
export function parseSq(pos: string): [number, number] | null {
  const m = /^(\d+),(\d+)$/.exec(pos);
  return m ? [Number(m[1]), Number(m[2])] : null;
}

interface Props {
  geo: Geometry;
  tokens: Record<string, string>; // suspect -> position
  weapons: Record<string, string>; // weapon -> room
  players?: SeatInfo[];
  highlights?: string[]; // legal move targets (rooms or "r,c")
  here?: string | null;
  you?: string | null; // viewer's suspect token (legend "← you")
  onPick?: (target: string) => void;
  legend?: boolean;
}

interface RoomBox { cells: Set<string>; r0: number; r1: number; c0: number; c1: number; mid: number }

export default function Board({ geo, tokens, weapons, players, highlights = [], here, you, onPick, legend = true }: Props) {
  const hl = useMemo(() => new Set(highlights), [highlights]);
  const rooms = useMemo(() => {
    const out: Record<string, RoomBox> = {};
    for (const [room, cells] of Object.entries(geo.rooms)) {
      const rs = cells.map((c) => c[0]), cs = cells.map((c) => c[1]);
      const r0 = Math.min(...rs), r1 = Math.max(...rs), c0 = Math.min(...cs), c1 = Math.max(...cs);
      // name row = middle row of the widest full row (the main rectangle), as the TUI does
      const rowsFull = [];
      for (let r = r0; r <= r1; r++) { let n = 0; for (let c = c0; c <= c1; c++) if (cells.some((x) => x[0] === r && x[1] === c)) n++; if (n === c1 - c0 + 1) rowsFull.push(r); }
      const mid = rowsFull.length ? rowsFull[Math.floor((rowsFull.length - 1) / 2)] : Math.floor((r0 + r1) / 2);
      out[room] = { cells: new Set(cells.map((c) => c.join(","))), r0, r1, c0, c1, mid };
    }
    return out;
  }, [geo]);
  const roomOf = useMemo(() => { const m: Record<string, string> = {}; for (const [room, b] of Object.entries(rooms)) for (const k of b.cells) m[k] = room; return m; }, [rooms]);
  const corridor = useMemo(() => new Set(geo.corridor.map((c) => c.join(","))), [geo]);
  const doors = useMemo(() => new Set(geo.doors.map((d) => d.cell.join(","))), [geo]);
  const seatBySuspect = useMemo(() => Object.fromEntries((players ?? []).map((p) => [p.suspect_token, p])), [players]);
  const [cr0, cr1, cc0, cc1] = geo.cellar;

  // overlays keyed by "r,c"
  const tokenAt: Record<string, string> = {};
  const inRoom: Record<string, string[]> = {};
  for (const [s, pos] of Object.entries(tokens)) { const rc = parseSq(pos); if (rc) tokenAt[rc.join(",")] = s; else (inRoom[pos] ??= []).push(s); }
  for (const [room, list] of Object.entries(inRoom)) { const b = rooms[room]; if (!b) continue; list.forEach((s, i) => { tokenAt[`${b.mid + 1},${b.c0 + 1 + i}`] = s; }); }
  const weaponAt: Record<string, string> = {};
  const byRoom: Record<string, string[]> = {};
  for (const [w, room] of Object.entries(weapons)) (byRoom[room] ??= []).push(w);
  for (const [room, ws] of Object.entries(byRoom)) { const b = rooms[room]; if (!b) continue; ws.slice(0, 3).forEach((w, i) => { weaponAt[`${b.r1},${b.c0 + i}`] = w; }); }
  // room name sits on the middle row, starting at the cell that centres it (it overflows across the room cells)
  const labelAt: Record<string, { room: string; text: string }> = {};
  for (const [room, b] of Object.entries(rooms)) {
    const name = SHORT[room] ?? room.toUpperCase();
    const cellsWide = name.length * 0.62; // monospace glyph ≈ 0.62 cell
    const start = Math.max(b.c0, b.c0 + Math.round((b.c1 - b.c0 + 1 - cellsWide) / 2));
    labelAt[`${b.mid},${start}`] = { room, text: name };
  }
  const passageAt: Record<string, string> = {};
  for (const room of Object.keys(geo.passages)) { const b = rooms[room]; if (b) passageAt[`${b.r1},${b.c1}`] = geo.passages[room]; }

  const cells: React.ReactNode[] = [];
  for (let r = 0; r < geo.rows; r++) {
    for (let c = 0; c < geo.cols; c++) {
      const key = `${r},${c}`;
      const room = roomOf[key];
      let cls = "sq", text = " ", title = "", click: (() => void) | undefined, style: React.CSSProperties | undefined;
      if (room) {
        const isHl = hl.has(room);
        cls = `sq room${isHl ? " hl" : ""}${here === room ? " here" : ""} ${Object.keys(rooms).indexOf(room) % 2 ? "rb" : "ra"}`;
        title = room;
        if (isHl && onPick) click = () => onPick(room);
        if (labelAt[key]) { text = labelAt[key].text; cls += " rname"; }
        else if (Object.values(labelAt).length && (() => { for (let d = 1; d < 9; d++) { const l = labelAt[`${r},${c - d}`]; if (l && l.room === room && l.text.length * 0.62 > d) return true; } return false; })()) cls += " under"; // covered by the overflowing label
        if (weaponAt[key]) { text = weaponAt[key][0].toLowerCase(); cls += " weapon"; title = `${weaponAt[key]} (in the ${room})`; }
        if (passageAt[key]) { text = "⇄"; cls += " passage"; title = `secret passage to the ${passageAt[key]}`; }
      } else if (r >= cr0 && r <= cr1 && c >= cc0 && c <= cc1) {
        cls = "sq cellar"; text = "░";
      } else if (corridor.has(key)) {
        const isHl = hl.has(key);
        cls = `sq cell${doors.has(key) ? " door" : ""}${isHl ? " hl" : ""}`;
        text = isHl ? "◆" : doors.has(key) ? "▢" : "·";
        title = isHl ? `move to ${key}` : key;
        if (isHl && onPick) click = () => onPick(key);
      }
      const tok = tokenAt[key];
      if (tok) {
        const seat = seatBySuspect[tok];
        cls += " token";
        text = tokenGlyph(tok);
        style = { background: tokenColor(tok), color: ["M", "W", "G"].includes(tokenLetter(tok)) ? "#111" : "#fff", opacity: seat?.eliminated ? 0.45 : 1 };
        title = `${tok}${seat ? ` — ${seat.id} (${seat.label})${seat.eliminated ? ", eliminated" : ""}` : ""}`;
      }
      cells.push(<span key={key} className={cls} style={style} title={title || undefined} onClick={click}>{text}</span>);
    }
  }
  const suspects = players ? players.map((p) => p.suspect_token) : Object.keys(tokens);
  return (
    <div className="tboard-wrap">
      <div className="tboard" role="img" aria-label="Clue board" style={{ gridTemplateColumns: `2.2em repeat(${geo.cols}, var(--cell))` }}>
        <span className="hdr" />
        {Array.from({ length: geo.cols }, (_, c) => <span key={c} className="hdr">{c}</span>)}
        {Array.from({ length: geo.rows }, (_, r) => [<span key={`h${r}`} className="hdr">{r}</span>, ...cells.slice(r * geo.cols, (r + 1) * geo.cols)])}
      </div>
      {legend && (
        <div className="tlegend">
          {suspects.map((s) => { const seat = seatBySuspect[s]; return <div key={s}><span className="token" style={{ background: tokenColor(s), color: ["M", "W", "G"].includes(tokenLetter(s)) ? "#111" : "#fff" }}>{tokenGlyph(s)}</span> {s}{seat ? <span className="dim"> {seat.id} {seat.label}{seat.name ? ` · ${seat.name}` : ""}</span> : null}{s === you ? <span className="accent"> ← you</span> : null}{seat?.eliminated ? <span className="bad"> ✗ out</span> : null}</div>; })}
          <div className="dim"><span className="door">▢</span> door&nbsp;&nbsp; <span className="passage">⇄</span> passage&nbsp;&nbsp; <span className="hlk">◆</span> reachable&nbsp;&nbsp; <span>░</span> cellar&nbsp;&nbsp; <span className="weapon">c</span> weapon</div>
        </div>
      )}
    </div>
  );
}

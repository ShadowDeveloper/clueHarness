import { useMemo } from "react";
import type { Board as Geometry, SeatInfo } from "../api/types";

const TOKEN_LETTER: Record<string, string> = { "Miss Scarlet": "S", "Col. Mustard": "M", "Mrs. White": "W", "Dr. Orchid": "W", "Mr. Green": "G", "Mrs. Peacock": "K", "Prof. Plum": "P" };
const TOKEN_COLOR: Record<string, string> = { S: "var(--S)", M: "var(--M)", W: "var(--W)", G: "var(--G)", K: "var(--K)", P: "var(--P)" };
const SHORT: Record<string, string> = { "Dining Room": "DINING", "Billiard Room": "BILLIARD", Conservatory: "CONSERV.", Kitchen: "KITCHEN", Ballroom: "BALLROOM", Lounge: "LOUNGE", Hall: "HALL", Study: "STUDY", Library: "LIBRARY" };
const WEAPON_SHORT: Record<string, string> = { Candlestick: "candle", Dagger: "dagger", Knife: "knife", "Lead Pipe": "pipe", Revolver: "revolver", Rope: "rope", Wrench: "wrench" };

export function tokenLetter(suspect: string): string { return TOKEN_LETTER[suspect] ?? suspect[0]; }
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
  onPick?: (target: string) => void;
}

export default function Board({ geo, tokens, weapons, players, highlights = [], here, onPick }: Props) {
  const hl = useMemo(() => new Set(highlights), [highlights]);
  const roomRects = useMemo(() => {
    // rooms may be unions of rectangles; draw each cell but label at the centroid
    const out: Record<string, { cells: [number, number][]; cx: number; cy: number }> = {};
    for (const [room, cells] of Object.entries(geo.rooms)) {
      const cx = cells.reduce((a, c) => a + c[1], 0) / cells.length + 0.5;
      const cy = cells.reduce((a, c) => a + c[0], 0) / cells.length + 0.5;
      out[room] = { cells, cx, cy };
    }
    return out;
  }, [geo]);
  const doorSet = useMemo(() => new Set(geo.doors.map((d) => d.cell.join(","))), [geo]);
  const seatBySuspect = useMemo(() => Object.fromEntries((players ?? []).map((p) => [p.suspect_token, p])), [players]);

  // tokens in a room: fan out around the centroid
  const inRoom: Record<string, string[]> = {};
  for (const [s, pos] of Object.entries(tokens)) if (!parseSq(pos)) (inRoom[pos] ??= []).push(s);
  const weaponsIn: Record<string, string[]> = {};
  for (const [w, room] of Object.entries(weapons)) (weaponsIn[room] ??= []).push(w);

  return (
    <svg className="board" viewBox={`0 0 ${geo.cols} ${geo.rows}`} role="img" aria-label="Clue board">
      <rect x={geo.cellar[2]} y={geo.cellar[0]} width={geo.cellar[3] - geo.cellar[2] + 1} height={geo.cellar[1] - geo.cellar[0] + 1} className="cellar" />
      {geo.corridor.map(([r, c]) => {
        const key = `${r},${c}`;
        const isHl = hl.has(key);
        return <rect key={key} x={c} y={r} width={1} height={1} className={`cell${doorSet.has(key) ? " door" : ""}${isHl ? " hl" : ""}`} onClick={isHl && onPick ? () => onPick(key) : undefined}>{isHl ? <title>move to {key}</title> : null}</rect>;
      })}
      {Object.entries(roomRects).map(([room, { cells, cx, cy }]) => {
        const isHl = hl.has(room);
        return (
          <g key={room} onClick={isHl && onPick ? () => onPick(room) : undefined}>
            {cells.map(([r, c]) => <rect key={`${r},${c}`} x={c} y={r} width={1} height={1} className={`room${isHl ? " hl" : ""}${here === room ? " here" : ""}`} />)}
            <text x={cx} y={cy - 1.6} className="label">{SHORT[room] ?? room.toUpperCase()}</text>
            {(weaponsIn[room] ?? []).map((w, i, arr) => <text key={w} x={cx + (i - (arr.length - 1) / 2) * 3.4} y={cy + 2.1} className="weapon">{WEAPON_SHORT[w] ?? w}</text>)}
            {(inRoom[room] ?? []).map((s, i, arr) => <Token key={s} suspect={s} x={cx + (i - (arr.length - 1) / 2) * 2.2} y={cy} seat={seatBySuspect[s]} />)}
            {isHl ? <title>enter the {room}</title> : null}
          </g>
        );
      })}
      {Object.entries(geo.passages).map(([a, b]) => (a < b ? <line key={a} x1={roomRects[a]?.cx} y1={roomRects[a]?.cy + 3.4} x2={roomRects[b]?.cx} y2={roomRects[b]?.cy + 3.4} className="passage" /> : null))}
      {Object.entries(tokens).map(([s, pos]) => {
        const rc = parseSq(pos);
        return rc ? <Token key={s} suspect={s} x={rc[1] + 0.5} y={rc[0] + 0.5} seat={seatBySuspect[s]} /> : null;
      })}
    </svg>
  );
}

function Token({ suspect, x, y, seat }: { suspect: string; x: number; y: number; seat?: SeatInfo }) {
  const L = tokenLetter(suspect);
  const dark = L === "M" || L === "W";
  return (
    <g className="token" opacity={seat?.eliminated ? 0.4 : 1}>
      <circle cx={x} cy={y} r={0.95} fill={tokenColor(suspect)} stroke="#000" strokeWidth={0.15} />
      <text x={x} y={y + 0.05} fill={dark ? "#111" : "#fff"}>{L}</text>
      <title>{suspect}{seat ? ` — ${seat.id} (${seat.label})${seat.eliminated ? ", eliminated" : ""}` : ""}</title>
    </g>
  );
}

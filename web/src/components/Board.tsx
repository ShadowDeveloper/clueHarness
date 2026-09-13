import { useMemo } from "react";
import type { Board as Geometry, SeatInfo } from "../api/types";

/** Graphical board (SVG). Same information as the TUI's board_render.py — corridor, doors, secret passages, cellar,
 *  room names, weapons, tokens, reachable squares — drawn as a Tudor Mansion floor plan. */

// Same letters as the TUI (board_render.TOKEN_LABELS): classic six + the large edition's film cast
const TOKEN_LETTER: Record<string, string> = {
  "Miss Scarlet": "S", "Col. Mustard": "M", "Mrs. White": "W", "Dr. Orchid": "W", "Mr. Green": "G", "Mrs. Peacock": "K", "Prof. Plum": "P",
  Wadsworth: "B", Yvette: "Y", "Miss Peach": "H", "Sgt. Gray": "A", "Mr. Boddy": "T", "Madame Rose": "R",
};
const TOKEN_COLOR: Record<string, string> = {
  S: "#c8102e", M: "#d9a41b", W: "#e9e4d8", G: "#2e7d4f", K: "#1f4fa0", P: "#6a2a7b",
  B: "#8d8d8d", Y: "#3fb8c9", H: "#f0a050", A: "#4a4f57", T: "#5a1010", R: "#b03060",
};
const SHORT: Record<string, string> = { "Dining Room": "Dining", "Billiard Room": "Billiards", Conservatory: "Conservatory", "Carriage House": "Carriage" };
// weapons as small brass tags with a two/three-letter abbreviation (emoji are not reliable across platforms)
const WEAPON_TAG: Record<string, string> = {
  Candlestick: "CDL", Dagger: "DGR", Knife: "KNF", "Lead Pipe": "PIPE", Revolver: "REV", Rope: "ROPE", Wrench: "WR",
  Poison: "PSN", Horseshoe: "SHOE", Axe: "AXE", Trophy: "TRPH", Poker: "PKR", "Garden Shears": "SHRS",
};
const FLOOR: Record<string, string> = {
  Hall: "tiles", Kitchen: "tiles", Garage: "tiles", Cellar: "cellarp", Courtyard: "grass", Gazebo: "grass",
  Lounge: "carpet", Study: "carpet", Library: "carpet", Attic: "carpet",
};

export function tokenLetter(suspect: string): string { return TOKEN_LETTER[suspect] ?? suspect[0]; }
export function tokenColor(suspect: string): string { return TOKEN_COLOR[tokenLetter(suspect)] ?? "#ccc"; }
export function tokenGlyph(suspect: string): string { return tokenLetter(suspect); }

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
  you?: string | null;
  onPick?: (target: string) => void;
  legend?: boolean;
}

interface RoomBox { cells: [number, number][]; r0: number; r1: number; c0: number; c1: number; cx: number; cy: number }

export default function Board({ geo, tokens, weapons, players, highlights = [], here, you, onPick, legend = true }: Props) {
  const hl = useMemo(() => new Set(highlights), [highlights]);
  const rooms = useMemo(() => {
    const out: Record<string, RoomBox> = {};
    for (const [room, cells] of Object.entries(geo.rooms)) {
      const rs = cells.map((c) => c[0]), cs = cells.map((c) => c[1]);
      const r0 = Math.min(...rs), r1 = Math.max(...rs), c0 = Math.min(...cs), c1 = Math.max(...cs);
      out[room] = { cells, r0, r1, c0, c1, cx: (c0 + c1 + 1) / 2, cy: (r0 + r1 + 1) / 2 };
    }
    return out;
  }, [geo]);
  const roomOf = useMemo(() => { const m: Record<string, string> = {}; for (const [room, b] of Object.entries(rooms)) for (const c of b.cells) m[c.join(",")] = room; return m; }, [rooms]);
  const doorSet = useMemo(() => new Set(geo.doors.map((d) => d.cell.join(","))), [geo]);
  const seatBySuspect = useMemo(() => Object.fromEntries((players ?? []).map((p) => [p.suspect_token, p])), [players]);
  const [cr0, cr1, cc0, cc1] = geo.cellar ?? [0, -1, 0, -1];

  // walls: edges of room cells that face a non-room cell (drawn as thick lines); door cells get an opening
  const walls = useMemo(() => {
    const segs: { x1: number; y1: number; x2: number; y2: number; door: boolean }[] = [];
    for (const [room, b] of Object.entries(rooms)) {
      for (const [r, c] of b.cells) {
        const nb: [number, number, number, number, number, number][] = [[r - 1, c, c, r, c + 1, r], [r + 1, c, c, r + 1, c + 1, r + 1], [r, c - 1, c, r, c, r + 1], [r, c + 1, c + 1, r, c + 1, r + 1]];
        for (const [nr, nc, x1, y1, x2, y2] of nb) {
          if (roomOf[`${nr},${nc}`] === room) continue;
          segs.push({ x1, y1, x2, y2, door: doorSet.has(`${nr},${nc}`) && geo.doors.some((d) => d.cell[0] === nr && d.cell[1] === nc && d.rooms.includes(room)) });
        }
      }
    }
    return segs;
  }, [rooms, roomOf, doorSet, geo]);

  const inRoom: Record<string, string[]> = {};
  for (const [s, pos] of Object.entries(tokens)) if (!parseSq(pos)) (inRoom[pos] ??= []).push(s);
  const weaponsIn: Record<string, string[]> = {};
  for (const [w, room] of Object.entries(weapons)) (weaponsIn[room] ??= []).push(w);

  const W = geo.cols, H = geo.rows;
  return (
    <div className="board-wrap">
      <svg className="board" viewBox={`-0.6 -0.6 ${W + 1.2} ${H + 1.2}`} role="img" aria-label="Clue board">
        <defs>
          <pattern id="parquet" width="2" height="2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="2" height="2" fill="#5a3a22" /><rect width="1" height="2" fill="#63412a" /><line x1="0" y1="1" x2="2" y2="1" stroke="#4d301b" strokeWidth="0.08" />
          </pattern>
          <pattern id="carpet" width="1" height="1" patternUnits="userSpaceOnUse">
            <rect width="1" height="1" fill="#7a1e24" /><rect x="0.08" y="0.08" width="0.84" height="0.84" fill="none" stroke="#8f2a30" strokeWidth="0.06" />
          </pattern>
          <pattern id="tiles" width="2" height="2" patternUnits="userSpaceOnUse">
            <rect width="2" height="2" fill="#d9cfb8" /><rect width="1" height="1" fill="#2b2b2b" /><rect x="1" y="1" width="1" height="1" fill="#2b2b2b" />
          </pattern>
          <pattern id="grass" width="1" height="1" patternUnits="userSpaceOnUse">
            <rect width="1" height="1" fill="#4f6b3a" /><path d="M0.2 0.8 L0.35 0.4 M0.5 0.9 L0.6 0.5 M0.8 0.75 L0.9 0.35" stroke="#6d8f4e" strokeWidth="0.06" />
          </pattern>
          <pattern id="cellarp" width="1" height="1" patternUnits="userSpaceOnUse">
            <rect width="1" height="1" fill="#1a1512" /><line x1="0" y1="0.5" x2="1" y2="0.5" stroke="#26201b" strokeWidth="0.1" />
          </pattern>
          <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0.08" dy="0.12" stdDeviation="0.12" floodColor="#000" floodOpacity="0.6" /></filter>
          <radialGradient id="tokenShine" cx="35%" cy="30%" r="70%"><stop offset="0" stopColor="#fff" stopOpacity="0.55" /><stop offset="0.5" stopColor="#fff" stopOpacity="0.05" /><stop offset="1" stopColor="#000" stopOpacity="0.35" /></radialGradient>
        </defs>
        {/* mansion outline */}
        <rect x={-0.6} y={-0.6} width={W + 1.2} height={H + 1.2} rx={0.5} fill="#1b1410" />
        <rect x={-0.15} y={-0.15} width={W + 0.3} height={H + 0.3} fill="#2a1f18" stroke="#c9a961" strokeWidth={0.12} />
        {/* corridor */}
        {geo.corridor.map(([r, c]) => {
          const key = `${r},${c}`, isHl = hl.has(key);
          return <rect key={key} x={c + 0.03} y={r + 0.03} width={0.94} height={0.94} rx={0.08} className={`cell${doorSet.has(key) ? " door" : ""}${isHl ? " hl" : ""}`} onClick={isHl && onPick ? () => onPick(key) : undefined}><title>{isHl ? `move to ${key}` : key}</title></rect>;
        })}
        {/* cellar (envelope) */}
        {geo.cellar && <>
        <rect x={cc0} y={cr0} width={cc1 - cc0 + 1} height={cr1 - cr0 + 1} fill="url(#cellarp)" stroke="#3a2f27" strokeWidth={0.1} />
        <text x={(cc0 + cc1 + 1) / 2} y={(cr0 + cr1 + 1) / 2 - 0.3} className="cellar-label">CLUE</text>
        <text x={(cc0 + cc1 + 1) / 2} y={(cr0 + cr1 + 1) / 2 + 1.1} className="cellar-sub">✉ confidential</text>
        </>}
        {/* rooms */}
        {Object.entries(rooms).map(([room, b]) => {
          const isHl = hl.has(room);
          const floor = `url(#${FLOOR[room] ?? "parquet"})`;
          const weaponsHere = weaponsIn[room] ?? [];
          const toks = inRoom[room] ?? [];
          return (
            <g key={room} className={`room${isHl ? " hl" : ""}${here === room ? " here" : ""}`} onClick={isHl && onPick ? () => onPick(room) : undefined}>
              {b.cells.map(([r, c]) => <rect key={`${r},${c}`} x={c} y={r} width={1} height={1} fill={floor} />)}
              {b.cells.map(([r, c]) => <rect key={`o${r},${c}`} x={c} y={r} width={1} height={1} className="room-tint" />)}
              <text x={b.cx} y={b.cy - (toks.length ? 1.0 : 0.2)} className="room-label" textLength={Math.min((SHORT[room] ?? room).length * 0.62, b.c1 - b.c0 + 0.4)} lengthAdjust="spacingAndGlyphs">{SHORT[room] ?? room}</text>
              {weaponsHere.map((w, i) => (
                <g key={w} className="weapon" transform={`translate(${b.c0 + 0.35 + i * 1.75}, ${b.r1 + 0.15})`}>
                  <title>{w} (in the {room})</title>
                  <rect width={1.6} height={0.62} rx={0.12} />
                  <text x={0.8} y={0.33}>{WEAPON_TAG[w] ?? w.slice(0, 3).toUpperCase()}</text>
                </g>
              ))}
              {toks.map((s, i) => {
                const perRow = Math.max(1, Math.floor((b.c1 - b.c0 + 0.6) / 1.35));
                const row = Math.floor(i / perRow), col = i % perRow, n = Math.min(perRow, toks.length - row * perRow);
                return <Pawn key={s} suspect={s} x={b.cx + (col - (n - 1) / 2) * 1.35} y={b.cy + 0.55 + row * 1.25} seat={seatBySuspect[s]} />;
              })}
              {geo.passages[room] && <text x={b.c1 + 0.5} y={b.r0 + 0.75} className="passage"><title>secret passage to the {geo.passages[room]}</title>⇄</text>}
              {isHl && <title>enter the {room}</title>}
            </g>
          );
        })}
        {/* walls + door openings */}
        {walls.map((s, i) => <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} className={s.door ? "doorway" : "wall"} />)}
        {/* door leaves: a brass door drawn across each opening so doors are obvious at any size */}
        {walls.filter((s) => s.door).map((s, i) => {
          const horiz = s.y1 === s.y2;
          const mx = (s.x1 + s.x2) / 2, my = (s.y1 + s.y2) / 2;
          return (
            <g key={`d${i}`} className="doorleaf" transform={`translate(${mx}, ${my})${horiz ? "" : " rotate(90)"}`}>
              <rect x={-0.5} y={-0.11} width={1} height={0.22} rx={0.04} />
              <line x1={-0.36} y1={0} x2={0.36} y2={0} />
              <circle cx={0.28} cy={0} r={0.045} />
            </g>
          );
        })}
        {/* corridor tokens */}
        {Object.entries(tokens).map(([s, pos]) => { const rc = parseSq(pos); return rc ? <Pawn key={s} suspect={s} x={rc[1] + 0.5} y={rc[0] + 0.5} seat={seatBySuspect[s]} /> : null; })}
      </svg>
      {legend && (
        <div className="legend">
          {(players ? players.map((p) => p.suspect_token) : Object.keys(tokens)).map((s) => {
            const seat = seatBySuspect[s];
            return <div key={s} className={seat?.eliminated ? "dim" : ""}><span className="swatch" style={{ background: tokenColor(s) }} /> <b>{s}</b>{seat ? <span className="dim"> · {seat.id} {seat.label}{seat.name ? ` · ${seat.name}` : ""}</span> : null}{s === you ? <span className="accent"> ← you</span> : null}{seat?.eliminated ? " ✗" : ""}</div>;
          })}
          <div className="dim keys">◻ door · ⇄ secret passage · <span className="hlk">◆</span> gold = reachable · brass tags = weapons in their rooms</div>
        </div>
      )}
    </div>
  );
}

function Pawn({ suspect, x, y, seat }: { suspect: string; x: number; y: number; seat?: SeatInfo }) {
  const col = tokenColor(suspect);
  const L = tokenLetter(suspect);
  return (
    <g className="token" opacity={seat?.eliminated ? 0.4 : 1} filter="url(#shadow)">
      <ellipse cx={x} cy={y + 0.32} rx={0.42} ry={0.16} fill={col} stroke="#000" strokeWidth={0.05} />
      <path d={`M ${x - 0.3} ${y + 0.3} L ${x - 0.16} ${y - 0.1} A 0.26 0.26 0 1 1 ${x + 0.16} ${y - 0.1} L ${x + 0.3} ${y + 0.3} Z`} fill={col} stroke="#000" strokeWidth={0.05} />
      <path d={`M ${x - 0.3} ${y + 0.3} L ${x - 0.16} ${y - 0.1} A 0.26 0.26 0 1 1 ${x + 0.16} ${y - 0.1} L ${x + 0.3} ${y + 0.3} Z`} fill="url(#tokenShine)" />
      <text x={x} y={y + 0.2} className="pawn-letter" fill={L === "M" || L === "W" ? "#111" : "#fff"}>{L}</text>
      <title>{suspect}{seat ? ` — ${seat.id} (${seat.label})${seat.eliminated ? ", eliminated" : ""}` : ""}</title>
    </g>
  );
}

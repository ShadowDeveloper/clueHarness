import type { Action, Board, Catalog, CoachHints, GameCreated, GameListItem, PlayerSpec, ReplayFrames, ReplayInfo, TournamentStatus } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(method: string, path: string, body?: unknown, params?: Record<string, string | undefined>): Promise<T> {
  const qs = params ? "?" + new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>).toString() : "";
  const r = await fetch(`/api${path}${qs}`, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* ignore */ }
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; version: string; games: number; cost: Record<string, number> }>("GET", "/health"),
  board: () => req<Board>("GET", "/board"),
  catalog: () => req<Catalog>("GET", "/catalog"),
  createGame: (body: { players?: PlayerSpec[]; players_arg?: string; seed?: number | null; config?: Record<string, unknown>; ponder?: boolean; delay?: number; provider?: string | null; autosave?: boolean; resume?: string }) => req<GameCreated>("POST", "/games", body),
  listGames: () => req<GameListItem[]>("GET", "/games"),
  listSaves: () => req<{ name: string; seed: number; turn: number; players: string[]; labels: string[]; mtime: number }[]>("GET", "/saves"),
  act: (id: string, k: string, body: { request_id: number; action?: Action; card?: string; player?: string }) => req<{ ok: boolean }>("POST", `/games/${id}/act`, body, { k }),
  control: (id: string, k: string, body: { pause?: boolean; delay?: number; acknowledge_seat?: string }) => req<{ ok: boolean }>("POST", `/games/${id}/control`, body, { k }),
  coach: (id: string, k: string, player?: string) => req<CoachHints>("POST", `/games/${id}/coach`, undefined, { k, player }),
  note: (id: string, k: string, note: string, player?: string) => req<{ notes: string[] }>("PUT", `/games/${id}/notes`, { note, player }, { k }),
  save: (id: string, k: string, name?: string) => req<{ ok: boolean; path: string }>("POST", `/games/${id}/save`, { name }, { k }),
  stop: (id: string, k: string) => req<{ ok: boolean; path: string | null }>("DELETE", `/games/${id}`, undefined, { k }),
  listReplays: () => req<{ name: string; size: number; mtime: number; redacted: boolean }[]>("GET", "/replays"),
  openReplay: (name: string) => req<ReplayInfo>("POST", "/replays/open", { name }),
  replayFrames: (id: string, viewer?: string) => req<ReplayFrames>("GET", `/replays/${id}/frames`, undefined, { viewer }),
  createTournament: (body: { players_arg?: string; players?: PlayerSpec[]; games: number; seed: number; workers: number; ponder?: boolean; provider?: string | null; max_usd?: number | null }) => req<TournamentStatus>("POST", "/tournaments", body),
  listTournaments: () => req<Omit<TournamentStatus, "report">[]>("GET", "/tournaments"),
  tournament: (id: string) => req<TournamentStatus>("GET", `/tournaments/${id}`),
  cancelTournament: (id: string) => req<{ ok: boolean }>("DELETE", `/tournaments/${id}`),
};

export function wsUrl(path: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}${path}`;
}

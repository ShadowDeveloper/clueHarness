// Hand-written mirrors of clue/web/schemas.py + game_session.py frames (kept small and explicit).

export type Card = string;

export interface PlayerSpec {
  id: string;
  name?: string | null;
  kind: "human" | "baseline" | "llm";
  bot?: string | null;
  model?: string | null;
  strategy?: string | null;
  temperature?: number | null;
  tools?: boolean;
  tool_mode?: string | null;
  prompt_profile?: string;
}

export interface Action {
  type: "roll" | "move" | "passage" | "suggest" | "accuse" | "end_turn" | "show_card";
  player?: string;
  to?: string;
  suspect?: string;
  weapon?: string;
  room?: string;
  card?: string;
}

export interface SeatInfo {
  id: string;
  name: string | null;
  label: string;
  kind: string;
  suspect_token: string;
  position: string;
  eliminated: boolean;
  hand_size: number;
}

export interface Notebook {
  viewer: string;
  my_hand: Card[];
  faceup: Card[];
  known_holder: Record<Card, string>;
  not_held: Record<string, Card[]>;
  has_one_of: { player: string; cards: Card[] }[];
  notes: string[];
  [k: string]: unknown;
}

export interface OmniRow { card: Card; truth: string; knows: Record<string, string>; }
export interface Omniscient { solution: Card[]; hands: Record<string, Card[]>; rows: OmniRow[]; candidates: Record<string, number | null>; }

export interface GameState {
  id: string;
  seed: number;
  viewer: string;
  seat_visible: boolean;
  turn: { number: number; current_player: string; phase: string; roll: number | null; pending_suggestion: null | { suggester: string; suspect: string; weapon: string; room: string; [k: string]: unknown }; acting: string | null };
  board: { token_positions: Record<string, string>; weapon_positions: Record<string, string>; players: SeatInfo[] };
  cards: { suspects: Card[]; weapons: Card[]; rooms: Card[]; faceup: Card[] };
  config: Record<string, unknown> & { dice: number; edition: string };
  finished: boolean;
  winner: string | null;
  paused: boolean;
  delay: number;
  humans: string[];
  hotseat: boolean;
  active_seat: string | null;
  handoff_pending: string | null;
  n_events: number;
  illegal_attempts: Record<string, number>;
  error: string | null;
  stopped: boolean;
  autosave: string | null;
  ponder: Record<string, unknown>;
  llm: Record<string, Record<string, number>>;
  you?: { id: string; hand: Card[]; position: string; eliminated: boolean; may_suggest: boolean; suspect_token: string };
  notebook?: Notebook;
  candidates?: number | null;
  omniscient?: Omniscient;
}

export interface GameEvent { seq: number; type: string; turn: number; player: string | null; text: string; [k: string]: unknown; }

export interface PendingRequest {
  request_id: number;
  kind: "action" | "card";
  legal: Action[];
  cards: Card[];
  pending_suggestion: GameState["turn"]["pending_suggestion"];
  roll: number | null;
}

export interface Finished { summary: Record<string, unknown> & { winner: string | null; solution: Card[]; turns: number }; replays: string[]; solution: Card[]; }

export type Frame =
  | ({ type: "snapshot"; state: GameState; events: GameEvent[]; request: PendingRequest | null; pending_for: string | null; handoff_pending: string | null; active_seat: string | null; finished?: Finished })
  | { type: "events"; events: GameEvent[]; state: GameState }
  | { type: "request"; request: PendingRequest | null; pending_for: string | null; handoff_pending: string | null; active_seat: string | null }
  | { type: "control"; paused: boolean; delay: number }
  | ({ type: "finished" } & Finished)
  | { type: "stopped"; resumable: string | null }
  | { type: "error"; message: string }
  | { type: "pong" };

export interface GameCreated { id: string; owner_token: string; spectator_token: string; seats: { id: string; label: string; kind: string; name: string | null }[]; humans: string[]; resumed: boolean; restored: string[]; }
export interface GameListItem { id: string; seed: number; players: string[]; labels: Record<string, string>; humans: string[]; finished: boolean; turn: number; created: number; winner: string | null; }

export interface Board { rows: number; cols: number; rooms: Record<string, [number, number][]>; corridor: [number, number][]; doors: { cell: [number, number]; rooms: string[] }[]; passages: Record<string, string>; cellar: number[]; starts: Record<string, [number, number]>; }

export interface Catalog {
  kinds: string[]; bots: string[]; strategies: string[]; tool_modes: string[]; prompt_profiles: string[]; providers: string[];
  default_provider: string; default_model: string; known_models: string[]; config_defaults: Record<string, unknown>; hotseat: boolean;
  cards: { suspects: Card[]; weapons: Card[]; rooms: Card[] };
}

export interface CoachHints { candidates: number; most_likely: null | { suspect: string; weapon: string; room: string; p: number }; deductions: string[]; expert_action: null | { key: string; action: Action }; error: string | null; }

export interface ReplayInfo { id: string; name: string; n_events: number; players: { id: string; [k: string]: unknown }[]; viewers: string[]; edition: string; }
export interface ReplayFrame { idx: number; tokens: Record<string, string>; weapons: Record<string, string>; eliminated: string[]; event: (GameEvent & Record<string, unknown>) | null; text: string; }
export interface ReplayFrames { info: ReplayInfo; frames: ReplayFrame[]; hands: Record<string, Card[]>; solution: Card[]; seat: Record<string, string>; weapon_start: Record<string, string>; private_records: Record<string, unknown>[]; }

export interface TournamentRow { agent: string; games: number; wins: number; win_rate: number; false_accusation_rate: number | null; avg_turns_to_win: number | null; avg_suggestions_per_game?: number; illegal_attempts: number | null; elo?: number; win_ci95?: [number, number]; [k: string]: unknown; }
export interface TournamentReport { games: number; seed: number; table: TournamentRow[]; results: { seed: number; winner_label: string | null; turns: number; seats: Record<string, string> }[]; pairwise?: Record<string, unknown>; curves: Record<string, number[]>; fingerprints?: Record<string, unknown>; }
export interface TournamentStatus { id: string; status: "running" | "finished" | "cancelled" | "error"; games: number; done: number; seed: number; players: string[]; started: number; finished_at: number | null; error: string | null; report: TournamentReport | null; cost: Record<string, number>; }
export type TournamentFrame = ({ type: "snapshot" } & TournamentStatus) | { type: "progress"; done: number; games: number; seed: number; winner_label: string | null; turns: number } | ({ type: "done" } & TournamentStatus) | { type: "pong" };

import type { GameState, PendingRequest } from "../api/types";

export const state: GameState = {
  id: "abc", seed: 1, viewer: "P1", seat_visible: true,
  turn: { number: 1, current_player: "P1", phase: "start", roll: null, pending_suggestion: null, acting: "P1" },
  board: { token_positions: { "Miss Scarlet": "24,7", "Col. Mustard": "17,0", "Mrs. White": "0,9" }, weapon_positions: { Rope: "Hall" }, players: [
    { id: "P1", name: null, label: "human", kind: "human", suspect_token: "Miss Scarlet", position: "24,7", eliminated: false, hand_size: 6 },
    { id: "P2", name: null, label: "baseline:expert", kind: "baseline", suspect_token: "Col. Mustard", position: "17,0", eliminated: false, hand_size: 6 },
    { id: "P3", name: null, label: "baseline:heuristic", kind: "baseline", suspect_token: "Mrs. White", position: "0,9", eliminated: false, hand_size: 6 },
  ] },
  cards: { suspects: ["Miss Scarlet", "Col. Mustard", "Mrs. White", "Mr. Green", "Mrs. Peacock", "Prof. Plum"], weapons: ["Candlestick", "Knife", "Lead Pipe", "Revolver", "Rope", "Wrench"], rooms: ["Kitchen", "Ballroom", "Conservatory", "Dining Room", "Lounge", "Hall", "Study", "Library", "Billiard Room"], faceup: [] },
  config: { dice: 2, edition: "classic" }, finished: false, winner: null, paused: false, delay: 0.6, humans: ["P1"], hotseat: false, active_seat: "P1", handoff_pending: null,
  n_events: 1, illegal_attempts: {}, error: null, stopped: false, autosave: null, ponder: {}, llm: {},
  you: { id: "P1", hand: ["Knife", "Hall"], position: "24,7", eliminated: false, may_suggest: false, suspect_token: "Miss Scarlet" },
  notebook: { viewer: "P1", my_hand: ["Knife", "Hall"], faceup: [], known_holder: { Knife: "P1", Hall: "P1", Rope: "P2" }, not_held: { P3: ["Rope"] }, has_one_of: [{ player: "P3", cards: ["Wrench", "Study"] }], notes: [] },
  candidates: 100,
};

export const rollReq: PendingRequest = { request_id: 1, kind: "action", legal: [{ type: "roll", player: "P1" }, { type: "accuse", player: "P1" }], cards: [], pending_suggestion: null, roll: null };
export const moveReq: PendingRequest = { request_id: 2, kind: "action", legal: [{ type: "move", player: "P1", to: "Lounge" }, { type: "move", player: "P1", to: "19,7" }, { type: "move", player: "P1", to: "20,8" }], cards: [], pending_suggestion: null, roll: 5 };
export const roomReq: PendingRequest = { request_id: 3, kind: "action", legal: [{ type: "suggest", player: "P1" }, { type: "accuse", player: "P1" }, { type: "end_turn", player: "P1" }], cards: [], pending_suggestion: null, roll: 5 };
export const cardReq: PendingRequest = { request_id: 4, kind: "card", legal: [], cards: ["Knife", "Hall"], pending_suggestion: { suggester: "P2", suspect: "Miss Scarlet", weapon: "Knife", room: "Hall" }, roll: null };

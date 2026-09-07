import { reduce } from "../ws/useGameSocket";
import type { GameView } from "../ws/useGameSocket";
import { state, rollReq } from "./fixtures";

const init: GameView = { state: null, events: [], request: null, pendingFor: null, handoffPending: null, finished: null, stopped: false, error: null, connected: false };

test("snapshot then events de-duplicate by seq and keep candidates", () => {
  let v = reduce(init, { type: "snapshot", state, events: [{ seq: 0, type: "game_start", turn: 0, player: null, text: "start" }], request: rollReq, pending_for: "P1", handoff_pending: null, active_seat: "P1" });
  expect(v.request?.request_id).toBe(1);
  const light = { ...state, candidates: null };
  v = reduce(v, { type: "events", events: [{ seq: 0, type: "game_start", turn: 0, player: null, text: "start" }, { seq: 1, type: "roll", turn: 1, player: "P1", text: "P1 rolled 5" }], state: light });
  expect(v.events.map((e) => e.seq)).toEqual([0, 1]);
  expect(v.state?.candidates).toBe(100); // light frame must not erase the last known count
  v = reduce(v, { type: "request", request: null, pending_for: "P2", handoff_pending: null, active_seat: "P1" });
  expect(v.request).toBeNull();
  v = reduce(v, { type: "finished", summary: { winner: "P2", solution: ["a", "b", "c"], turns: 9 }, replays: [], solution: ["a", "b", "c"] });
  expect(v.finished?.summary.winner).toBe("P2");
  expect(v.state?.finished).toBe(true);
});

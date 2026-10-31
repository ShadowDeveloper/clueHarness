// TypeScript port of clue/tools/analyst.py (+ the deduction/opponent helpers it uses) so the analyst
// page works without a backend — e.g. on the static GitHub Pages deployment. Mirrors the Python
// report shape; cross-validated by __tests__/analyst.fixtures.test.ts.

import { allCards, categoryOf, EDITION_IDS, editionDef, nDealt } from "./cards";
import { emptyNotebook, hardDeductions, markNotHeld, NotebookLite, solve, Solution } from "./solver";

export interface SuggestionObservation {
  type: "suggestion";
  suggester: string;
  suspect: string;
  weapon: string;
  room: string;
  disprover?: string | null;
  shown_card?: string | null;
}

export interface FactObservation {
  type: "fact";
  player: string;
  card: string;
  has: boolean;
}

export type Observation = SuggestionObservation | FactObservation;

export interface AnalysisSession {
  edition: string;
  players: string[];
  me: string;
  my_cards: string[];
  faceup: string[];
  hand_sizes?: Record<string, number> | null;
  observations: Observation[];
}

export function emptySession(): AnalysisSession {
  return { edition: "classic", players: [], me: "", my_cards: [], faceup: [], hand_sizes: null, observations: [] };
}

export function observationLabel(ob: Observation): string {
  if (ob.type === "fact") return `fact: ${ob.player} ${ob.has ? "holds" : "lacks"} ${ob.card}`;
  const tail = ob.shown_card ? `${ob.disprover} showed ${ob.shown_card}` : ob.disprover ? `${ob.disprover} disproved` : "nobody disproved";
  return `${ob.suggester}: ${ob.suspect} / ${ob.weapon} / ${ob.room} -> ${tail}`;
}

// ---------------------------------------------------------------- validation + hand sizes

export function defaultHandSizesFor(session: AnalysisSession): Record<string, number> {
  if (session.hand_sizes && Object.keys(session.hand_sizes).length > 0) return { ...session.hand_sizes };
  const pool = nDealt(session.edition) - session.faceup.length;
  const others = session.players.filter((p) => p !== session.me);
  const out: Record<string, number> = {};
  if (session.players.includes(session.me) && session.my_cards.length > 0) {
    const mine = session.my_cards.length;
    const base = Math.floor(Math.max(pool - mine, 0) / Math.max(others.length, 1));
    const rem = Math.max(pool - mine, 0) % Math.max(others.length, 1);
    others.forEach((p, i) => (out[p] = base + (i < rem ? 1 : 0)));
    out[session.me] = mine;
    const ordered: Record<string, number> = {};
    for (const p of session.players) ordered[p] = out[p];
    return ordered;
  }
  const base = Math.floor(pool / Math.max(session.players.length, 1));
  const rem = pool % Math.max(session.players.length, 1);
  session.players.forEach((p, i) => (out[p] = base + (i < rem ? 1 : 0)));
  return out;
}

export function validateSession(session: AnalysisSession): string[] {
  const errors: string[] = [];
  if (!EDITION_IDS.includes(session.edition as (typeof EDITION_IDS)[number])) {
    return [`unknown edition '${session.edition}'; choose one of ${EDITION_IDS.join(", ")}`];
  }
  const ed = session.edition;
  const deck = new Set(allCards(ed));
  const nMax = editionDef(ed).maxPlayers;
  if (session.players.length < 3 || session.players.length > nMax) errors.push(`${ed} edition needs 3..${nMax} players (got ${session.players.length})`);
  if (new Set(session.players).size !== session.players.length) errors.push("player names must be unique");
  if (!session.players.includes(session.me)) errors.push(`your seat '${session.me}' is not in the player list`);
  for (const [label, cards] of [["my_cards", session.my_cards], ["faceup", session.faceup]] as const) {
    for (const c of cards) if (!deck.has(c)) errors.push(`${label}: '${c}' is not a ${ed}-edition card`);
  }
  if (session.my_cards.some((c) => session.faceup.includes(c))) errors.push("a card cannot be both in your hand and face-up");
  if (session.hand_sizes && Object.keys(session.hand_sizes).length > 0) {
    const keys = Object.keys(session.hand_sizes);
    const expected = nDealt(ed) - session.faceup.length;
    if (keys.length !== session.players.length || !session.players.every((p) => keys.includes(p))) errors.push("hand_sizes must cover exactly the listed players");
    else if (Object.values(session.hand_sizes).reduce((a, b) => a + b, 0) !== expected) errors.push(`hand sizes must sum to ${expected} (deck minus envelope and face-up)`);
    else if (session.my_cards.length > 0 && session.hand_sizes[session.me] !== session.my_cards.length)
      errors.push(`hand_sizes[${session.me}] = ${session.hand_sizes[session.me]} but you entered ${session.my_cards.length} cards`);
  }
  session.observations.forEach((ob, i) => {
    const where = `observation ${i + 1}`;
    if (ob.type === "suggestion") {
      if (!session.players.includes(ob.suggester)) errors.push(`${where}: unknown suggester '${ob.suggester}'`);
      if (ob.disprover != null && !session.players.includes(ob.disprover)) errors.push(`${where}: unknown disprover '${ob.disprover}'`);
      if (ob.disprover != null && ob.disprover === ob.suggester) errors.push(`${where}: the suggester cannot disprove their own suggestion`);
      for (const [card, cat] of [[ob.suspect, "suspect"], [ob.weapon, "weapon"], [ob.room, "room"]] as const) {
        if (categoryOf(card, ed) !== cat) errors.push(`${where}: '${card}' is not a ${ed}-edition ${cat}`);
      }
      if (ob.shown_card != null) {
        if (ob.disprover == null) errors.push(`${where}: shown_card given but nobody disproved`);
        else if (![ob.suspect, ob.weapon, ob.room].includes(ob.shown_card)) errors.push(`${where}: shown card '${ob.shown_card}' is not one of the three suggested cards`);
      }
    } else {
      if (!session.players.includes(ob.player)) errors.push(`${where}: unknown player '${ob.player}'`);
      if (!deck.has(ob.card)) errors.push(`${where}: '${ob.card}' is not a ${ed}-edition card`);
    }
  });
  return errors;
}

// ---------------------------------------------------------------- session -> notebook + events

export interface HistoryEvent {
  type: string;
  turn: number;
  player?: string;
  suspect?: string;
  weapon?: string;
  room?: string;
  disprover?: string;
  suggester?: string;
  card?: string;
}

export function sessionEvents(session: AnalysisSession): HistoryEvent[] {
  const events: HistoryEvent[] = [];
  const order = session.players;
  session.observations.forEach((ob, idx) => {
    if (ob.type !== "suggestion") return;
    const turn = idx + 1;
    events.push({ type: "suggest", turn, player: ob.suggester, suspect: ob.suspect, weapon: ob.weapon, room: ob.room });
    const start = order.indexOf(ob.suggester);
    const ring = Array.from({ length: order.length - 1 }, (_, k) => order[(start + k + 1) % order.length]);
    if (ob.disprover == null) {
      for (const p of ring) events.push({ type: "cannot_disprove", turn, player: p });
      events.push({ type: "no_one_disproved", turn, player: ob.suggester, suspect: ob.suspect, weapon: ob.weapon, room: ob.room });
      return;
    }
    for (const p of ring) {
      if (p === ob.disprover) break;
      events.push({ type: "cannot_disprove", turn, player: p });
    }
    const ev: HistoryEvent = { type: "disproved", turn, player: ob.disprover, disprover: ob.disprover, suggester: ob.suggester };
    if (ob.shown_card != null) ev.card = ob.shown_card;
    events.push(ev);
  });
  return events;
}

export function buildNotebook(session: AnalysisSession): { nb: NotebookLite; conflicts: string[] } {
  const nb = emptyNotebook(session.me);
  nb.myHand = [...session.my_cards];
  nb.faceup = [...session.faceup];
  const conflicts: string[] = [];
  for (const c of session.my_cards) nb.knownHolder[c] = session.me;
  const pending = new Map<number, [string, string, string]>();
  for (const ev of sessionEvents(session)) {
    if (ev.type === "suggest") pending.set(ev.turn, [ev.suspect!, ev.weapon!, ev.room!]);
    else if (ev.type === "cannot_disprove") markNotHeld(nb, ev.player!, pending.get(ev.turn) ?? []);
    else if (ev.type === "disproved") {
      if (ev.card != null) nb.knownHolder[ev.card] = ev.disprover!;
      else nb.hasOneOf.push({ player: ev.disprover!, cards: [...(pending.get(ev.turn) ?? [])] });
    } else if (ev.type === "no_one_disproved") {
      const cards = [ev.suspect!, ev.weapon!, ev.room!];
      nb.unrefuted.push({ player: ev.player!, cards });
      for (const p of session.players) if (p !== ev.player) markNotHeld(nb, p, cards);
    }
  }
  for (const ob of session.observations) {
    if (ob.type !== "fact") continue;
    if (ob.has) {
      const prev = nb.knownHolder[ob.card];
      if (prev !== undefined && prev !== ob.player) conflicts.push(`${ob.card} cannot be held by both ${prev} and ${ob.player}`);
      else nb.knownHolder[ob.card] = ob.player;
    } else {
      markNotHeld(nb, ob.player, [ob.card]);
    }
  }
  for (const [card, holder] of Object.entries(nb.knownHolder).sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
    if ((nb.notHeld[holder] ?? []).includes(card)) conflicts.push(`${holder} is marked both holding and not holding ${card}`);
    if (nb.faceup.includes(card)) conflicts.push(`${card} is face-up but also assigned to ${holder}`);
  }
  return { nb, conflicts };
}

// ---------------------------------------------------------------- deduction helpers (ports)

export interface SuggestionEV {
  suspect: string;
  weapon: string;
  room: string;
  novelty: number;
  possible_disprovers: number;
  first_unknown_disprover: string | null;
  own_cards_included: number;
  score: number;
}

export function suggestionEv(nb: NotebookLite, players: string[], me: string, suspect: string, weapon: string, room: string): SuggestionEV {
  const cards = [suspect, weapon, room];
  const known = new Set([...nb.myHand, ...nb.faceup, ...Object.keys(nb.knownHolder)]);
  const novelty = cards.filter((c) => !known.has(c)).length / 3;
  const meIdx = players.indexOf(me);
  const order = [...players.slice(meIdx + 1), ...players.slice(0, meIdx)];
  let possibleDisprovers = 0;
  let firstUnknown: string | null = null;
  for (const p of order) {
    const excluded = new Set(nb.notHeld[p] ?? []);
    const could = cards.filter((c) => !excluded.has(c) && nb.knownHolder[c] !== me);
    if (could.length > 0) {
      possibleDisprovers += 1;
      if (firstUnknown === null && could.some((c) => nb.knownHolder[c] === undefined)) firstUnknown = p;
    }
  }
  const mineIn = cards.filter((c) => nb.myHand.includes(c)).length;
  const score = 0.5 * novelty + 0.3 * (possibleDisprovers / Math.max(1, players.length - 1)) + 0.2 * (1 - mineIn / 3);
  return {
    suspect,
    weapon,
    room,
    novelty: round3(novelty),
    possible_disprovers: possibleDisprovers,
    first_unknown_disprover: firstUnknown,
    own_cards_included: mineIn,
    score: round3(score),
  };
}

export function bestSuggestion(nb: NotebookLite, players: string[], me: string, room: string, edition: string): SuggestionEV {
  const d = editionDef(edition);
  let best: SuggestionEV | null = null;
  for (const s of d.suspects) {
    for (const w of d.weapons) {
      const ev = suggestionEv(nb, players, me, s, w, room);
      if (best === null || ev.score > best.score) best = ev;
    }
  }
  return best!;
}

// ---------------------------------------------------------------- opponent threat (port of clue/tools/opponent.py)

export interface ThreatReport {
  opponents: Record<string, { n_possible: number; p_win_next_turn: number; unrefuted: boolean; repeat_suggestion: boolean; known_cards: number }>;
  max_threat: number;
  most_dangerous: string | null;
  p_any_wins_before_my_turn: number;
}

function shadowNotebook(nb: NotebookLite, sol: Solution, me: string, opp: string, players: string[], history: HistoryEvent[]): NotebookLite {
  const hp = sol.holderProbs;
  const sh = emptyNotebook(opp);
  sh.faceup = [...nb.faceup];
  for (const [card, probs] of Object.entries(hp)) {
    if ((probs[opp] ?? 0) >= 0.999) {
      sh.myHand.push(card);
      sh.knownHolder[card] = opp;
    }
  }
  const pending = new Map<number, string[]>();
  for (const ev of history) {
    const turn = ev.turn ?? 0;
    const who = String(ev.player);
    if (ev.type === "suggest") pending.set(turn, [ev.suspect!, ev.weapon!, ev.room!]);
    else if (ev.type === "cannot_disprove") {
      if (pending.has(turn)) markNotHeld(sh, who, pending.get(turn)!);
    } else if (ev.type === "disproved") {
      const cards = pending.get(turn) ?? [];
      const shower = String(ev.disprover ?? ev.player);
      if (cards.length === 0 || shower === "None") continue;
      const suggester = String(ev.suggester);
      if (shower === opp) continue; // they showed a card: tells them nothing new
      if (suggester === opp) {
        if (ev.card != null && shower === me) sh.knownHolder[ev.card] = shower;
        else {
          let best = cards[0];
          for (const c of cards) if ((hp[c]?.[shower] ?? 0) > (hp[best]?.[shower] ?? 0)) best = c;
          if ((hp[best]?.[shower] ?? 0) > 0) sh.knownHolder[best] = shower;
          else sh.hasOneOf.push({ player: shower, cards });
        }
      } else {
        sh.hasOneOf.push({ player: shower, cards });
      }
    } else if (ev.type === "no_one_disproved") {
      const cards = [ev.suspect!, ev.weapon!, ev.room!];
      sh.unrefuted.push({ player: who, cards });
      for (const p of players) if (p !== who) markNotHeld(sh, p, cards);
    }
  }
  return sh;
}

export function opponentThreat(
  nb: NotebookLite,
  players: string[],
  me: string,
  handSizes: Record<string, number>,
  edition: string,
  history: HistoryEvent[],
  sol: Solution,
): ThreatReport {
  const out: ThreatReport = { opponents: {}, max_threat: 0, most_dangerous: null, p_any_wins_before_my_turn: 0 };
  const triplesByPlayer = new Map<string, string[]>();
  for (const ev of history) {
    if (ev.type === "suggest") {
      const key = String(ev.player);
      const arr = triplesByPlayer.get(key) ?? [];
      arr.push([ev.suspect, ev.weapon, ev.room].join("|"));
      triplesByPlayer.set(key, arr);
    }
  }
  const unrefutedBy = new Set(nb.unrefuted.slice(-players.length).map((c) => c.player));
  let bestP = 0;
  let worst: string | null = null;
  for (const opp of players) {
    if (opp === me) continue;
    const sh = shadowNotebook(nb, sol, me, opp, players, history);
    const ssol = solve(sh, players, handSizes, edition);
    const n = Math.max(1, ssol.nPossible);
    const unknownHand = Math.max(0, (handSizes[opp] ?? 0) - sh.myHand.length);
    const nEst = Math.max(1, Math.round(n * Math.pow(0.75, unknownHand)));
    const seq = triplesByPlayer.get(opp) ?? [];
    const repeat = seq.length >= 2 && seq[seq.length - 1] === seq[seq.length - 2];
    const unref = unrefutedBy.has(opp);
    let p = nEst === 1 ? 1.0 : nEst <= 3 ? 0.5 / nEst : 0.0;
    if (unref) p = Math.max(p, 0.5);
    if (repeat) p = Math.max(p, 0.35);
    out.opponents[opp] = { n_possible: nEst, p_win_next_turn: round3(p), unrefuted: unref, repeat_suggestion: repeat, known_cards: Object.keys(sh.knownHolder).length };
    if (p > bestP) {
      bestP = p;
      worst = opp;
    }
  }
  out.max_threat = round3(bestP);
  out.most_dangerous = worst;
  let q = 1.0;
  for (const d of Object.values(out.opponents)) q *= 1.0 - d.p_win_next_turn;
  out.p_any_wins_before_my_turn = round3(1.0 - q);
  return out;
}

// ---------------------------------------------------------------- full report

export interface AnalysisReport {
  ok: boolean;
  errors: string[];
  edition: string;
  players: string[];
  me: string;
  hand_sizes: Record<string, number>;
  consistent: boolean;
  conflicts: string[];
  solution: {
    n_possible: number;
    combos: { suspect: string; weapon: string; room: string; p: number }[];
    cards: Record<string, number>;
    best: [string, string, string] | null;
    best_prob: number;
    exact: boolean;
  };
  holders: Record<string, Record<string, number>>;
  deductions: string[];
  unseen: { suspects: string[]; weapons: string[]; rooms: string[] };
  threat: ThreatReport;
  guide: {
    accusal: { accuse: boolean; best: [string, string, string] | null; confidence: number; n_possible: number; threshold: number; exact: boolean };
    suggestions: SuggestionEV[];
    advice: string[];
  };
}

function round3(x: number): number {
  return Math.round(x * 1000) / 1000;
}

function round4(x: number): number {
  return Math.round(x * 10000) / 10000;
}

export function analyze(session: AnalysisSession, accuseThreshold = 0.9, topSuggestions = 3): AnalysisReport {
  const base: AnalysisReport = {
    ok: false,
    errors: [],
    edition: session.edition,
    players: session.players,
    me: session.me,
    hand_sizes: {},
    consistent: false,
    conflicts: [],
    solution: { n_possible: 0, combos: [], cards: {}, best: null, best_prob: 0, exact: true },
    holders: {},
    deductions: [],
    unseen: { suspects: [], weapons: [], rooms: [] },
    threat: { opponents: {}, max_threat: 0, most_dangerous: null, p_any_wins_before_my_turn: 0 },
    guide: { accusal: { accuse: false, best: null, confidence: 0, n_possible: 0, threshold: accuseThreshold, exact: true }, suggestions: [], advice: [] },
  };
  const errors = validateSession(session);
  if (errors.length > 0) return { ...base, errors };
  const ed = session.edition;
  const d = editionDef(ed);
  const sizes = defaultHandSizesFor(session);
  const { nb, conflicts } = buildNotebook(session);
  const knownNotInSolution = new Set([...nb.myHand, ...nb.faceup, ...Object.keys(nb.knownHolder)]);
  const unseen = {
    suspects: d.suspects.filter((c) => !knownNotInSolution.has(c)),
    weapons: d.weapons.filter((c) => !knownNotInSolution.has(c)),
    rooms: d.rooms.filter((c) => !knownNotInSolution.has(c)),
  };
  if (conflicts.length > 0) {
    return {
      ...base,
      ok: true,
      hand_sizes: sizes,
      conflicts,
      unseen,
      guide: {
        ...base.guide,
        advice: ["Your observations are contradictory - at least one entry must be wrong:", ...conflicts.map((c) => `  - ${c}`)],
      },
    };
  }
  const sol = solve(nb, session.players, sizes, ed);
  const cards: Record<string, number> = {};
  for (const [c, p] of Object.entries(sol.cardProbs).sort((a, b) => b[1] - a[1])) if (p > 0) cards[c] = round4(p);
  const best = sol.combos.length > 0 ? ([sol.combos[0].suspect, sol.combos[0].weapon, sol.combos[0].room] as [string, string, string]) : null;
  const bestProb = sol.combos.length > 0 ? round4(sol.combos[0].p) : 0;
  const solution = {
    n_possible: sol.nPossible,
    combos: sol.combos.slice(0, 10).map((c) => ({ ...c, p: round4(c.p) })),
    cards,
    best,
    best_prob: bestProb,
    exact: sol.exact,
  };
  const holders: Record<string, Record<string, number>> = {};
  for (const [c, probs] of Object.entries(sol.holderProbs)) {
    holders[c] = {};
    for (const [h, p] of Object.entries(probs)) holders[c][h] = round4(p);
  }
  const deductions = hardDeductions(sol, nb);
  const accusal = {
    accuse: sol.nPossible > 0 && bestProb >= accuseThreshold,
    best,
    confidence: bestProb,
    n_possible: sol.nPossible,
    threshold: accuseThreshold,
    exact: sol.exact,
  };
  const threat = opponentThreat(nb, session.players, session.me, sizes, ed, sessionEvents(session), sol);
  const ranked: SuggestionEV[] = d.rooms.map((room) => bestSuggestion(nb, session.players, session.me, room, ed));
  ranked.sort((a, b) => b.score - a.score || (a.room < b.room ? -1 : 1));
  const suggestions = ranked.slice(0, topSuggestions);
  return {
    ...base,
    ok: true,
    hand_sizes: sizes,
    consistent: sol.nPossible > 0,
    solution,
    holders,
    deductions,
    unseen,
    threat,
    guide: { accusal, suggestions, advice: advice(solution, accusal, deductions, threat, suggestions) },
  };
}

function fmt2(x: number): string {
  return x.toFixed(2);
}

function advice(
  solution: AnalysisReport["solution"],
  accusal: AnalysisReport["guide"]["accusal"],
  deductions: string[],
  threat: ThreatReport,
  top: SuggestionEV[],
): string[] {
  const lines: string[] = [];
  const n = solution.n_possible;
  if (n === 0) return ["Your observations are contradictory - at least one entry must be wrong. Re-check the most recent suggestion/fact you added."];
  const best = solution.best;
  if (n === 1 && solution.exact && best) {
    lines.push(`SOLVED - the envelope must be ${best[0]} / ${best[1]} / ${best[2]}. Accuse on your turn.`);
    return lines;
  }
  if (best) {
    const qual = solution.exact ? "" : " (estimated - large table)";
    lines.push(`${n} candidate solutions remain${qual}; most likely: ${best[0]} / ${best[1]} / ${best[2]} at p=${fmt2(solution.best_prob)}.`);
  }
  if (accusal.accuse && accusal.best) {
    lines.push(`Confidence ${fmt2(accusal.confidence)} >= ${fmt2(accusal.threshold)}: accusing ${accusal.best[0]} / ${accusal.best[1]} / ${accusal.best[2]} is justified if you accept the risk.`);
  } else {
    lines.push(`Too early to accuse (confidence ${fmt2(accusal.confidence)} < ${fmt2(accusal.threshold)}). Keep suggesting to narrow it down.`);
  }
  if (deductions.length > 0) lines.push("Mark in your notebook: " + deductions.slice(0, 3).join("; ") + (deductions.length > 3 ? "..." : "."));
  if (top.length > 0) {
    const t = top[0];
    lines.push(`Highest-value next suggestion: ${t.suspect} with the ${t.weapon} in the ${t.room} (score ${fmt2(t.score)}).`);
  }
  if (threat.max_threat >= 0.35 && threat.most_dangerous) {
    lines.push(`Danger: ${threat.most_dangerous} looks close to solving (p~${fmt2(threat.max_threat)} before your next turn). Consider accusing earlier than usual.`);
  }
  return lines;
}

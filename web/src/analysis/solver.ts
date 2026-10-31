// TypeScript port of clue/tools/solver.py so the analyst runs fully client-side (GitHub Pages has no
// backend). Same model: the deck minus face-up cards is partitioned into the envelope (one suspect, one
// weapon, one room) and the players' hands of known sizes; we count every complete assignment consistent
// with the evidence per envelope combo (BigInt - counts overflow 2^53 early in a game). Big tables
// (>6 players or the 36-card Large deck) use sound constraint propagation + deterministic sampling,
// exactly like the Python solver; `exact` identifies which path produced the result.
// Cross-validated against the Python implementation by src/analysis/__tests__/fixtures.json.

import { allCards, editionDef, nDealt } from "./cards";

export const ENVELOPE = "envelope";

export interface Constraint {
  player: string;
  cards: string[];
}

/** The viewer's evidence, mirroring clue/manager/notebook.py (fields the solver consumes). */
export interface NotebookLite {
  viewer: string;
  myHand: string[];
  faceup: string[];
  knownHolder: Record<string, string>;
  notHeld: Record<string, string[]>;
  hasOneOf: Constraint[];
  unrefuted: Constraint[];
}

export function emptyNotebook(viewer: string): NotebookLite {
  return { viewer, myHand: [], faceup: [], knownHolder: {}, notHeld: {}, hasOneOf: [], unrefuted: [] };
}

export function markNotHeld(nb: NotebookLite, player: string, cards: string[]): void {
  const cur = (nb.notHeld[player] ||= []);
  for (const c of cards) if (!cur.includes(c)) cur.push(c);
}

export interface Solution {
  /** envelope candidates sorted by weight, probabilities normalised */
  combos: { suspect: string; weapon: string; room: string; p: number }[];
  nPossible: number;
  cardProbs: Record<string, number>; // P(card in envelope)
  holderProbs: Record<string, Record<string, number>>; // card -> holder (player | envelope | faceup) -> P
  certainHolder: Record<string, string>;
  exact: boolean;
}

const EXACT_MAX_PLAYERS = 6;
const EXACT_MAX_HEAD = 22;
const EXACT_MAX_CARDS = 21;
const SAMPLES = 400;
const SAMPLE_NODE_BUDGET = 150_000;

// ---------------------------------------------------------------- BigInt combinatorics

function comb(n: number, k: number): bigint {
  if (k < 0 || k > n) return 0n;
  let out = 1n;
  for (let i = 0; i < Math.min(k, n - k); i++) out = (out * BigInt(n - i)) / BigInt(i + 1);
  return out;
}

function multinomial(parts: number[]): bigint {
  let total = parts.reduce((a, b) => a + b, 0);
  let out = 1n;
  for (const k of parts) {
    out *= comb(total, k);
    total -= k;
  }
  return out;
}

function ratio(num: bigint, den: bigint): number {
  if (den === 0n) return 0;
  return Number((num * 1_000_000_000n) / den) / 1e9;
}

// ---------------------------------------------------------------- shared setup

export function defaultHandSizes(edition: string, players: string[], faceupCount: number): Record<string, number> {
  const pool = nDealt(edition) - faceupCount;
  const base = Math.floor(pool / players.length);
  const rem = pool % players.length;
  const out: Record<string, number> = {};
  players.forEach((p, i) => (out[p] = base + (i < rem ? 1 : 0)));
  return out;
}

interface Prepared {
  players: string[];
  sizes: Record<string, number>;
  known: Record<string, string>;
  notHeld: Record<string, Set<string>>;
  triples: Record<string, string[][]>;
  all: string[];
  faceup: Set<string>;
}

function prepare(nb: NotebookLite, players: string[], handSizes: Record<string, number> | null, edition: string): Prepared {
  const sizes = handSizes ?? defaultHandSizes(edition, players, nb.faceup.length);
  const all = allCards(edition);
  const known: Record<string, string> = { ...nb.knownHolder };
  const notHeld: Record<string, Set<string>> = {};
  for (const p of players) notHeld[p] = new Set(nb.notHeld[p] ?? []);
  const triples: Record<string, string[][]> = {};
  for (const p of players) triples[p] = [];
  const seen = new Set<string>();
  for (const con of nb.hasOneOf) {
    if (!(con.player in triples)) continue;
    const key = con.player + "\u0000" + [...con.cards].sort().join("\u0000");
    if (seen.has(key)) continue;
    seen.add(key);
    triples[con.player].push([...con.cards]);
  }
  return { players, sizes, known, notHeld, triples, all, faceup: new Set(nb.faceup) };
}

function emptySolution(exact: boolean): Solution {
  return { combos: [], nPossible: 0, cardProbs: {}, holderProbs: {}, certainHolder: {}, exact };
}

// ---------------------------------------------------------------- exact counting

export function solve(nb: NotebookLite, players: string[], handSizes: Record<string, number> | null, edition: string): Solution {
  const d = editionDef(edition);
  const prep = prepare(nb, players, handSizes, edition);
  const { sizes, known, notHeld, triples, all, faceup } = prep;
  const headCards = new Set<string>();
  for (const p of players) for (const t of triples[p]) for (const c of t) if (!(c in known)) headCards.add(c);
  if (players.length > EXACT_MAX_PLAYERS || headCards.size > EXACT_MAX_HEAD || all.length > EXACT_MAX_CARDS) {
    if (!propagate(prep)) return emptySolution(false);
    return solveSampled(prep, edition);
  }
  const mentioned = new Set<string>(Object.keys(known));
  for (const p of players) {
    for (const t of triples[p]) for (const c of t) mentioned.add(c);
    for (const c of notHeld[p]) mentioned.add(c);
  }
  const candEnv = {
    suspect: d.suspects.filter((c) => !(c in known) && !faceup.has(c)),
    weapon: d.weapons.filter((c) => !(c in known) && !faceup.has(c)),
    room: d.rooms.filter((c) => !(c in known) && !faceup.has(c)),
  };
  const baseCap: Record<string, number> = {};
  for (const p of players) baseCap[p] = sizes[p] - Object.values(known).filter((h) => h === p).length;
  if (Object.values(baseCap).some((v) => v < 0)) return emptySolution(true);
  const pool = all.filter((c) => !(c in known) && !faceup.has(c));
  const holderCounts: Record<string, Record<string, bigint>> = {};
  for (const c of pool) {
    holderCounts[c] = { [ENVELOPE]: 0n };
    for (const p of players) holderCounts[c][p] = 0n;
  }
  const combos: { env: [string, string, string]; count: bigint }[] = [];
  let total = 0n;
  const caps = players.map((p) => baseCap[p]);
  for (const s of candEnv.suspect)
    for (const w of candEnv.weapon)
      for (const r of candEnv.room) {
        const envSet = new Set([s, w, r]);
        const remaining = pool.filter((c) => !envSet.has(c));
        const constrained = remaining.filter((c) => mentioned.has(c));
        const freeCount = remaining.length - constrained.length;
        const effTriples = players.map((p) => {
          const mine = new Set(Object.entries(known).filter(([, h]) => h === p).map(([c]) => c));
          return triples[p].filter((t) => !t.some((c) => mine.has(c)));
        });
        const { count, perCard } = countAssignments(players, constrained, freeCount, caps, players.map((p) => notHeld[p]), effTriples);
        if (count === 0n) continue;
        combos.push({ env: [s, w, r], count });
        total += count;
        for (const c of [s, w, r]) holderCounts[c][ENVELOPE] += count;
        constrained.forEach((c, ci) => players.forEach((p, pi) => (holderCounts[c][p] += perCard[ci][pi])));
        if (freeCount > 0) {
          const free = remaining.filter((c) => !mentioned.has(c));
          players.forEach((p, pi) => {
            let load = 0n;
            for (let ci = 0; ci < constrained.length; ci++) load += perCard[ci][pi];
            const share = BigInt(baseCap[p]) * count - load;
            for (const c of free) holderCounts[c][p] += share / BigInt(freeCount);
          });
        }
      }
  const sol = emptySolution(true);
  if (total === 0n) return sol;
  combos.sort((a, b) => (b.count > a.count ? 1 : b.count < a.count ? -1 : 0)); // stable: ties keep deck/product order like Python's max()
  sol.nPossible = combos.length;
  sol.combos = combos.map(({ env, count }) => ({ suspect: env[0], weapon: env[1], room: env[2], p: ratio(count, total) }));
  for (const { env, count } of combos) for (const c of env) sol.cardProbs[c] = (sol.cardProbs[c] ?? 0) + ratio(count, total);
  for (const c of all) {
    if (c in known) {
      sol.holderProbs[c] = { [known[c]]: 1 };
      sol.certainHolder[c] = known[c];
    } else if (faceup.has(c)) {
      sol.holderProbs[c] = { faceup: 1 };
    } else {
      const probs: Record<string, number> = {};
      for (const [h, n] of Object.entries(holderCounts[c])) if (n > 0n) probs[h] = ratio(n, total);
      sol.holderProbs[c] = probs;
      const holders = Object.keys(probs);
      if (holders.length === 1) sol.certainHolder[c] = holders[0];
    }
    sol.cardProbs[c] = sol.cardProbs[c] ?? 0;
  }
  return sol;
}

function countAssignments(
  players: string[],
  constrained: string[],
  freeCount: number,
  caps: number[],
  notHeld: Set<string>[],
  triples: string[][][],
): { count: bigint; perCard: bigint[][] } {
  const n = players.length;
  const zero = constrained.map(() => players.map(() => 0n));
  if (caps.reduce((a, b) => a + b, 0) !== constrained.length + freeCount) return { count: 0n, perCard: zero };
  const inTriple = new Set<string>();
  for (const tl of triples) for (const t of tl) for (const c of t) inTriple.add(c);
  const head = constrained.filter((c) => inTriple.has(c));
  const tail = constrained.filter((c) => !inTriple.has(c));
  const maskOf = (card: string): number => {
    let m = 0;
    for (let pi = 0; pi < n; pi++) if (!notHeld[pi].has(card)) m |= 1 << pi;
    return m;
  };
  const tailGroupMap = new Map<number, number>();
  for (const c of tail) tailGroupMap.set(maskOf(c), (tailGroupMap.get(maskOf(c)) ?? 0) + 1);
  const groups: [number, number][] = [...tailGroupMap.entries()].sort((a, b) => a[0] - b[0]);

  const tailCache = new Map<string, bigint>();
  function tailWays(capsLeft: number[], groupsLeft: [number, number][]): bigint {
    if (groupsLeft.length === 0) return capsLeft.reduce((a, b) => a + b, 0) === freeCount ? multinomial(capsLeft) : 0n;
    const key = capsLeft.join(",") + "|" + groupsLeft.map(([m, k]) => `${m}:${k}`).join(";");
    const hit = tailCache.get(key);
    if (hit !== undefined) return hit;
    const [[mask, k], ...rest] = groupsLeft;
    const allowed: number[] = [];
    for (let pi = 0; pi < n; pi++) if ((mask >> pi) & 1) allowed.push(pi);
    let total = 0n;
    const cl = [...capsLeft];
    const split = (idx: number, left: number, mult: bigint): void => {
      if (idx === allowed.length) {
        if (left === 0) total += mult * tailWays(cl, rest);
        return;
      }
      const pi = allowed[idx];
      const max = Math.min(left, cl[pi]);
      for (let take = 0; take <= max; take++) {
        cl[pi] -= take;
        split(idx + 1, left - take, mult * comb(left, take));
        cl[pi] += take;
      }
    };
    split(0, k, 1n);
    tailCache.set(key, total);
    return total;
  }

  // unsat state: per player, indices of still-unsatisfied triples
  const unsat0: number[][] = triples.map((tl) => tl.map((_, i) => i));
  type Step = { caps: number[]; unsat: number[][] } | null;
  function step(i: number, capsLeft: number[], unsat: number[][], pi: number): Step {
    const card = head[i];
    if (capsLeft[pi] === 0 || notHeld[pi].has(card)) return null;
    const cl = [...capsLeft];
    cl[pi] -= 1;
    const newUnsat = unsat.map((u, q) => (q === pi && u.length > 0 ? u.filter((ti) => !triples[pi][ti].includes(card)) : u));
    const remaining = new Set(head.slice(i + 1));
    for (let q = 0; q < n; q++) {
      if (newUnsat[q].length > 0 && cl[q] === 0) return null;
      for (const ti of newUnsat[q]) {
        if (!triples[q][ti].some((x) => remaining.has(x) && !notHeld[q].has(x))) return null;
      }
    }
    return { caps: cl, unsat: newUnsat };
  }

  const stateKey = (i: number, capsLeft: number[], unsat: number[][]): string => i + "#" + capsLeft.join(",") + "#" + unsat.map((u) => u.join(".")).join("|");
  const backCache = new Map<string, bigint>();
  function back(i: number, capsLeft: number[], unsat: number[][]): bigint {
    if (i === head.length) {
      if (unsat.some((u) => u.length > 0)) return 0n;
      return tailWays(capsLeft, groups);
    }
    const key = stateKey(i, capsLeft, unsat);
    const hit = backCache.get(key);
    if (hit !== undefined) return hit;
    let total = 0n;
    for (let pi = 0; pi < n; pi++) {
      const nxt = step(i, capsLeft, unsat, pi);
      if (nxt) total += back(i + 1, nxt.caps, nxt.unsat);
    }
    backCache.set(key, total);
    return total;
  }

  const total = back(0, caps, unsat0);
  const per = new Map<string, bigint[]>();
  for (const c of constrained) per.set(c, players.map(() => 0n));
  if (total > 0n) {
    // forward pass over head cards for marginals
    let frontier = new Map<string, { caps: number[]; unsat: number[][]; ways: bigint }>();
    frontier.set(stateKey(0, caps, unsat0), { caps, unsat: unsat0, ways: 1n });
    for (let i = 0; i < head.length; i++) {
      const next = new Map<string, { caps: number[]; unsat: number[][]; ways: bigint }>();
      for (const { caps: cl, unsat: un, ways } of frontier.values()) {
        for (let pi = 0; pi < n; pi++) {
          const nxt = step(i, cl, un, pi);
          if (!nxt) continue;
          const b = back(i + 1, nxt.caps, nxt.unsat);
          if (b === 0n) continue;
          per.get(head[i])![pi] += ways * b;
          const key = stateKey(i + 1, nxt.caps, nxt.unsat);
          const cur = next.get(key);
          if (cur) cur.ways += ways;
          else next.set(key, { caps: nxt.caps, unsat: nxt.unsat, ways });
        }
      }
      frontier = next;
    }
    if (tail.length > 0) {
      for (const { caps: cl, unsat: un, ways } of frontier.values()) {
        if (un.some((u) => u.length > 0)) continue;
        groups.forEach(([mask], gi) => {
          for (let pi = 0; pi < n; pi++) {
            if (!((mask >> pi) & 1) || cl[pi] === 0) continue;
            const g2 = groups.map(([m, kk], j) => (j === gi ? ([m, kk - 1] as [number, number]) : ([m, kk] as [number, number]))).filter(([, kk]) => kk > 0);
            const cl2 = [...cl];
            cl2[pi] -= 1;
            const w = tailWays(cl2, g2);
            if (w > 0n) for (const c of tail) if (maskOf(c) === mask) per.get(c)![pi] += ways * w;
          }
        });
      }
    }
  }
  return { count: total, perCard: constrained.map((c) => per.get(c)!) };
}

// ---------------------------------------------------------------- big tables: propagation + sampling

function propagate(prep: Prepared): boolean {
  const { players, sizes, known, notHeld, triples, all, faceup } = prep;
  let changed = true;
  while (changed) {
    changed = false;
    for (const [card, holder] of Object.entries(known)) {
      for (const p of players) {
        if (p !== holder && !notHeld[p].has(card)) {
          notHeld[p].add(card);
          changed = true;
        }
      }
    }
    for (const p of players) {
      const mine = new Set(Object.entries(known).filter(([, h]) => h === p).map(([c]) => c));
      if (mine.size > sizes[p]) return false;
      if (mine.size === sizes[p]) {
        for (const c of all) {
          if (!mine.has(c) && !notHeld[p].has(c)) {
            notHeld[p].add(c);
            changed = true;
          }
        }
      }
      for (const t of triples[p]) {
        if (t.some((c) => mine.has(c))) continue;
        const cand = t.filter((c) => !notHeld[p].has(c) && !faceup.has(c) && (known[c] === undefined || known[c] === p));
        if (cand.length === 0) return false;
        if (cand.length === 1 && known[cand[0]] === undefined) {
          known[cand[0]] = p;
          changed = true;
        }
      }
    }
  }
  return true;
}

/** Deterministic 32-bit RNG (mulberry32) seeded from the evidence, like the Python sampled solver. */
function rngFrom(seedStr: string): () => number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seedStr.length; i++) {
    h ^= seedStr.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  let a = h >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffled<T>(arr: T[], rng: () => number): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function solveSampled(prep: Prepared, edition: string): Solution {
  const { players, sizes, known, notHeld, triples, all, faceup } = prep;
  const d = editionDef(edition);
  const sol = emptySolution(false);
  const nobody = new Set(all.filter((c) => !(c in known) && !faceup.has(c) && players.every((p) => notHeld[p].has(c))));
  const candEnv: Record<string, string[]> = {};
  for (const [cat, cards] of [["suspect", d.suspects], ["weapon", d.weapons], ["room", d.rooms]] as const) {
    const forced = cards.filter((c) => nobody.has(c));
    if (forced.length > 1) return sol;
    candEnv[cat] = forced.length > 0 ? forced : cards.filter((c) => !(c in known) && !faceup.has(c));
    if (candEnv[cat].length === 0) return sol;
  }
  const pool = all.filter((c) => !(c in known) && !faceup.has(c));
  const caps: Record<string, number> = {};
  for (const p of players) caps[p] = sizes[p] - Object.values(known).filter((h) => h === p).length;
  if (Object.values(caps).some((v) => v < 0)) return sol;
  const seed = JSON.stringify([edition, players, sizes, known, players.map((p) => [...notHeld[p]].sort()), players.map((p) => triples[p].map((t) => [...t].sort()))]);
  const rng = rngFrom(seed);
  const inTriple = new Set<string>();
  for (const p of players) for (const t of triples[p]) for (const c of t) inTriple.add(c);
  const comboCounts = new Map<string, number>();
  const holderCounts: Record<string, Record<string, number>> = {};
  for (const c of pool) {
    holderCounts[c] = { [ENVELOPE]: 0 };
    for (const p of players) holderCounts[c][p] = 0;
  }
  let nOk = 0;
  const nodesLeft = { v: SAMPLE_NODE_BUDGET };
  const choice = <T,>(arr: T[]): T => arr[Math.floor(rng() * arr.length)];
  for (let s = 0; s < SAMPLES && nodesLeft.v > 0; s++) {
    const env: [string, string, string] = [choice(candEnv.suspect), choice(candEnv.weapon), choice(candEnv.room)];
    const envSet = new Set(env);
    const deal = randomDeal(rng, players, caps, notHeld, triples, pool.filter((c) => !envSet.has(c)), inTriple, nodesLeft);
    if (!deal) continue;
    nOk += 1;
    const key = env.join("|");
    comboCounts.set(key, (comboCounts.get(key) ?? 0) + 1);
    for (const c of env) holderCounts[c][ENVELOPE] += 1;
    for (const [c, p] of deal) holderCounts[c][p] += 1;
  }
  if (nOk === 0) nOk = 1; // fall back to the propagation-only candidate set (uniform)
  // keep every surviving envelope candidate (smoothed) so the candidate set is never falsely tiny
  const combos: { env: [string, string, string]; count: number }[] = [];
  for (const s of candEnv.suspect)
    for (const w of candEnv.weapon)
      for (const r of candEnv.room) combos.push({ env: [s, w, r], count: (comboCounts.get([s, w, r].join("|")) ?? 0) * 4 + 1 });
  const total = combos.reduce((a, c) => a + c.count, 0);
  combos.sort((a, b) => b.count - a.count); // stable: ties keep product order
  sol.nPossible = combos.length;
  sol.combos = combos.map(({ env, count }) => ({ suspect: env[0], weapon: env[1], room: env[2], p: count / total }));
  for (const { env, count } of combos) for (const c of env) sol.cardProbs[c] = (sol.cardProbs[c] ?? 0) + count / total;
  for (const c of all) {
    sol.cardProbs[c] = sol.cardProbs[c] ?? 0;
    if (c in known) {
      sol.holderProbs[c] = { [known[c]]: 1 };
      sol.certainHolder[c] = known[c];
    } else if (faceup.has(c)) {
      sol.holderProbs[c] = { faceup: 1 };
    } else if (nobody.has(c)) {
      sol.holderProbs[c] = { [ENVELOPE]: 1 };
      sol.certainHolder[c] = ENVELOPE;
    } else {
      const probs: Record<string, number> = {};
      for (const [h, cnt] of Object.entries(holderCounts[c])) if (cnt > 0) probs[h] = cnt / nOk;
      sol.holderProbs[c] = probs;
    }
  }
  return sol;
}

function randomDeal(
  rng: () => number,
  players: string[],
  caps: Record<string, number>,
  notHeld: Record<string, Set<string>>,
  triples: Record<string, string[][]>,
  cards: string[],
  inTriple: Set<string>,
  nodesLeft: { v: number },
): Map<string, string> | null {
  const left: Record<string, number> = { ...caps };
  if (Object.values(left).reduce((a, b) => a + b, 0) !== cards.length) return null;
  let order = shuffled(cards.filter((c) => inTriple.has(c)), rng);
  order.sort((a, b) => players.filter((p) => !notHeld[p].has(a)).length - players.filter((p) => !notHeld[p].has(b)).length);
  order = [...order, ...shuffled(cards.filter((c) => !inTriple.has(c)), rng)];
  const unsat: Record<string, string[][]> = {};
  for (const p of players) unsat[p] = [...triples[p]];
  const deal = new Map<string, string>();
  let nodes = 0;
  const budget = Math.min(3000, nodesLeft.v);

  const feasible = (startIdx: number): boolean => {
    const rem = new Set(order.slice(startIdx));
    for (const q of players) {
      if (unsat[q].length > 0 && left[q] === 0) return false;
      for (const t of unsat[q]) if (!t.some((x) => rem.has(x) && !notHeld[q].has(x))) return false;
    }
    return true;
  };

  const rec = (i: number): boolean => {
    if (i === order.length) return players.every((p) => unsat[p].length === 0);
    nodes += 1;
    if (nodes > budget) return false;
    const card = order[i];
    const choices = shuffled(players.filter((p) => left[p] > 0 && !notHeld[p].has(card)), rng);
    choices.sort((a, b) => unsat[b].filter((t) => t.includes(card)).length - unsat[a].filter((t) => t.includes(card)).length);
    for (const p of choices) {
      left[p] -= 1;
      const saved = unsat[p];
      unsat[p] = saved.filter((t) => !t.includes(card));
      deal.set(card, p);
      if (feasible(i + 1) && rec(i + 1)) return true;
      deal.delete(card);
      unsat[p] = saved;
      left[p] += 1;
      if (nodes > budget) return false;
    }
    return false;
  };

  const ok = rec(0);
  nodesLeft.v -= nodes;
  return ok ? deal : null;
}

// ---------------------------------------------------------------- hard deductions

export function hardDeductions(sol: Solution, nb: NotebookLite): string[] {
  const out: string[] = [];
  for (const [card, holder] of Object.entries(sol.certainHolder).sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
    if (card in nb.knownHolder || nb.faceup.includes(card)) continue;
    out.push(holder === ENVELOPE ? `${card} is in the envelope` : `${holder} must hold ${card}`);
  }
  if (sol.nPossible === 1 && sol.combos.length === 1) {
    const c = sol.combos[0];
    out.push(`SOLVED: ${c.suspect} / ${c.weapon} / ${c.room}`);
  }
  return out;
}

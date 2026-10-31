// Analyst: enter a real-table game (your cards + observed suggestions) and get live probabilities,
// hard deductions, opponent threat, and coach-style guidance. All math runs client-side
// (src/analysis is a cross-validated port of the Python solver), so this page also works on the
// static GitHub Pages deployment where there is no backend.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AnalysisSession,
  analyze,
  emptySession,
  FactObservation,
  labelFor,
  Observation,
  observationLabel,
  SuggestionObservation,
} from "../analysis/analyst";
import { EDITION_IDS, EDITIONS, editionDef } from "../analysis/cards";

const STORE = "clue:analyst:session";
const NOBODY = "__nobody__";
const NOT_SEEN = "__not_seen__";

function load(): AnalysisSession {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) return { ...emptySession(), ...JSON.parse(raw) };
  } catch {
    /* corrupted storage: start fresh */
  }
  return { ...emptySession(), players: ["Me", "P2", "P3", "P4"], me: "Me" };
}

function pct(p: number | undefined): string {
  if (!p || p < 0.0005) return "";
  if (p >= 0.9995) return "100";
  return `${Math.round(p * 100)}`;
}

function heat(p: number | undefined): string {
  if (!p || p < 0.0005) return "transparent";
  const a = Math.min(0.85, 0.12 + p * 0.75);
  return `rgba(214, 69, 48, ${a.toFixed(3)})`;
}

export default function Analyze() {
  const [session, setSession] = useState<AnalysisSession>(load);
  const [playersText, setPlayersText] = useState(session.players.join(", "));
  const [tab, setTab] = useState<"suggestion" | "fact">("suggestion");
  const [showFaceup, setShowFaceup] = useState(session.faceup.length > 0);
  // draft suggestion / fact being entered
  const ed = useMemo(() => editionDef(EDITION_IDS.includes(session.edition as never) ? session.edition : "classic"), [session.edition]);
  const [sg, setSg] = useState({ suggester: "", suspect: "", weapon: "", room: "", disprover: NOBODY, shown: NOT_SEEN });
  const [fact, setFact] = useState({ player: "", has: true, card: "" });
  const [renaming, setRenaming] = useState(false);
  const [renameCard, setRenameCard] = useState("");
  const [renameLabel, setRenameLabel] = useState("");
  // true when the probability grid actually overflows sideways (phones / Large edition):
  // used to surface a swipe affordance, since mobile browsers hide scrollbars.
  const probRef = useRef<HTMLDivElement | null>(null);
  const [probOverflow, setProbOverflow] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORE, JSON.stringify(session));
  }, [session]);

  const report = useMemo(() => analyze(session), [session]);

  useEffect(() => {
    const check = () => {
      const el = probRef.current;
      setProbOverflow(!!el && el.scrollWidth > el.clientWidth + 1);
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [report]);
  const patch = (p: Partial<AnalysisSession>) => setSession((s) => ({ ...s, ...p }));
  const label = (c: string) => labelFor(session, c);
  const renames = session.card_names ?? {};

  const applyRename = () => {
    const card = renameCard || ed.suspects[0];
    const lab = renameLabel.trim();
    const next = { ...renames };
    if (!lab || lab === card) delete next[card];
    else next[card] = lab;
    patch({ card_names: next });
    setRenameLabel("");
  };
  const clearRename = (card: string) => {
    const next = { ...renames };
    delete next[card];
    patch({ card_names: next });
  };

  const applyPlayers = (text: string) => {
    const names = text.split(",").map((t) => t.trim()).filter(Boolean);
    const me = names.includes(session.me) ? session.me : names[0] ?? "";
    patch({ players: names, me });
  };

  const toggleCard = (key: "my_cards" | "faceup", card: string) => {
    const cur = session[key];
    const next = cur.includes(card) ? cur.filter((c) => c !== card) : [...cur, card];
    const other: Partial<AnalysisSession> = {};
    if (key === "my_cards" && session.faceup.includes(card)) other.faceup = session.faceup.filter((c) => c !== card);
    if (key === "faceup" && session.my_cards.includes(card)) other.my_cards = session.my_cards.filter((c) => c !== card);
    patch({ [key]: next, ...other });
  };

  // Touch-friendly face-up marking: with face-up mode on, each tap cycles the chip
  // none -> in my hand -> face-up -> none (shift-click still jumps straight to face-up).
  const cycleCard = (card: string) => {
    if (session.my_cards.includes(card)) {
      patch({ my_cards: session.my_cards.filter((c) => c !== card), faceup: [...session.faceup, card] });
    } else if (session.faceup.includes(card)) {
      patch({ faceup: session.faceup.filter((c) => c !== card) });
    } else {
      patch({ my_cards: [...session.my_cards, card] });
    }
  };

  const addObservation = (ob: Observation) => patch({ observations: [...session.observations, ob] });
  const removeObservation = (idx: number) => patch({ observations: session.observations.filter((_, i) => i !== idx) });

  const addSuggestion = () => {
    const ob: SuggestionObservation = {
      type: "suggestion",
      suggester: sg.suggester || session.players[0],
      suspect: sg.suspect || ed.suspects[0],
      weapon: sg.weapon || ed.weapons[0],
      room: sg.room || ed.rooms[0],
      disprover: sg.disprover === NOBODY ? null : sg.disprover,
      shown_card: sg.disprover === NOBODY || sg.shown === NOT_SEEN ? null : sg.shown,
    };
    addObservation(ob);
    setSg((d) => ({ ...d, disprover: NOBODY, shown: NOT_SEEN }));
  };

  const addFact = () => {
    const ob: FactObservation = { type: "fact", player: fact.player || session.players[0], has: fact.has, card: fact.card || ed.suspects[0] };
    addObservation(ob);
  };

  const exportSession = () => {
    const blob = new Blob([JSON.stringify(session, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "clue-analyst-session.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const importSession = (file: File) => {
    file.text().then((t) => {
      try {
        const s = { ...emptySession(), ...JSON.parse(t) } as AnalysisSession;
        setSession(s);
        setPlayersText(s.players.join(", "));
        setShowFaceup(s.faceup.length > 0);
      } catch {
        alert("not a valid session JSON");
      }
    });
  };

  const reset = () => {
    const s = { ...emptySession(), players: ["Me", "P2", "P3", "P4"], me: "Me" };
    setSession(s);
    setPlayersText(s.players.join(", "));
    setShowFaceup(false);
  };

  const sol = report.solution;
  const cardGroups: [string, string[]][] = [["Suspects", ed.suspects], ["Weapons", ed.weapons], ["Rooms", ed.rooms]];
  const suggestCards = [sg.suspect || ed.suspects[0], sg.weapon || ed.weapons[0], sg.room || ed.rooms[0]];

  return (
    <div className="page grid analyze-grid">
      <div className="grid" style={{ alignContent: "start" }}>
        <div className="panel">
          <h3>Your table</h3>
          <div className="row">
            <label className="dim">Edition</label>
            <select value={session.edition} onChange={(e) => patch({ edition: e.target.value, my_cards: [], faceup: [], observations: [], card_names: {} })}>
              {EDITION_IDS.map((id) => (
                <option key={id} value={id}>{EDITIONS[id].label}</option>
              ))}
            </select>
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <label className="dim">Players (seating order)</label>
            <input
              style={{ flex: 1, minWidth: 160 }}
              value={playersText}
              onChange={(e) => setPlayersText(e.target.value)}
              onBlur={() => applyPlayers(playersText)}
              onKeyDown={(e) => e.key === "Enter" && applyPlayers(playersText)}
              placeholder="Me, Alice, Bob, Cara"
            />
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <label className="dim">You are</label>
            <select value={session.me} onChange={(e) => patch({ me: e.target.value })}>
              {session.players.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <label className="dim" style={{ marginLeft: "auto" }}>
              <input type="checkbox" checked={showFaceup} onChange={(e) => { setShowFaceup(e.target.checked); if (!e.target.checked) patch({ faceup: [] }); }} /> face-up cards
            </label>
          </div>
          <div style={{ marginTop: 8 }}>
            <div className="dim" style={{ fontSize: 12 }}>
              Your hand ({session.my_cards.length}) — click to toggle{showFaceup ? "; tap again for face-up ◇, again to clear" : ""}
            </div>
            {cardGroups.map(([groupName, cards]) => (
              <div className="row" key={groupName} style={{ marginTop: 4 }}>
                <span className="dim" style={{ width: 64, fontSize: 11 }}>{groupName}</span>
                <span className="row" style={{ gap: 4 }}>
                  {cards.map((c) => (
                    <button
                      key={c}
                      className={`chip ${session.my_cards.includes(c) ? "mine" : ""} ${session.faceup.includes(c) ? "faceup" : ""}`}
                      title={session.faceup.includes(c) ? `${c} (face-up)` : c}
                      onClick={(e) => {
                        if (!showFaceup) toggleCard("my_cards", c);
                        else if (e.shiftKey) toggleCard("faceup", c);
                        else cycleCard(c);
                      }}
                    >
                      {label(c)}
                    </button>
                  ))}
                </span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 8 }}>
            <button className="linkish" onClick={() => setRenaming(!renaming)}>
              {renaming ? "▾" : "▸"} Rename cards ({Object.keys(renames).length}) — match your copy of the game
            </button>
            {renaming && (
              <div className="grid" style={{ gap: 6, marginTop: 6 }}>
                <div className="row rename-row">
                  <select value={renameCard || ed.suspects[0]} onChange={(e) => { setRenameCard(e.target.value); setRenameLabel((renames[e.target.value] ?? "").trim()); }}>
                    {cardGroups.map(([groupName, cards]) => (
                      <optgroup key={groupName} label={groupName}>
                        {cards.map((c) => <option key={c} value={c}>{renames[c] ? `${renames[c]} (${c})` : c}</option>)}
                      </optgroup>
                    ))}
                  </select>
                  <input
                    style={{ flex: 1, minWidth: 110 }}
                    placeholder="name on your cards"
                    value={renameLabel}
                    onChange={(e) => setRenameLabel(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && applyRename()}
                  />
                  <button className="primary" onClick={applyRename}>Set</button>
                </div>
                {Object.entries(renames).map(([c, v]) => (
                  <div className="row" key={c} style={{ fontSize: 12 }}>
                    <span className="dim">{c}</span> → <span>{v}</span>
                    <button title="restore standard name" style={{ marginLeft: "auto", padding: "0 6px", fontSize: 11 }} onClick={() => clearRename(c)}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="tabs">
            <button className={tab === "suggestion" ? "on" : ""} onClick={() => setTab("suggestion")}>Add suggestion</button>
            <button className={tab === "fact" ? "on" : ""} onClick={() => setTab("fact")}>Add fact</button>
          </div>
          {tab === "suggestion" ? (
            <div className="grid" style={{ gap: 6 }}>
              <div className="row">
                <select value={sg.suggester || session.players[0]} onChange={(e) => setSg({ ...sg, suggester: e.target.value })}>
                  {session.players.map((p) => <option key={p}>{p}</option>)}
                </select>
                <span className="dim">suggested</span>
                <select value={sg.suspect || ed.suspects[0]} onChange={(e) => setSg({ ...sg, suspect: e.target.value, shown: NOT_SEEN })}>
                  {ed.suspects.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                </select>
                <select value={sg.weapon || ed.weapons[0]} onChange={(e) => setSg({ ...sg, weapon: e.target.value, shown: NOT_SEEN })}>
                  {ed.weapons.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                </select>
                <select value={sg.room || ed.rooms[0]} onChange={(e) => setSg({ ...sg, room: e.target.value, shown: NOT_SEEN })}>
                  {ed.rooms.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                </select>
              </div>
              <div className="row">
                <span className="dim">disproved by</span>
                <select value={sg.disprover} onChange={(e) => setSg({ ...sg, disprover: e.target.value, shown: NOT_SEEN })}>
                  <option value={NOBODY}>nobody</option>
                  {session.players.filter((p) => p !== (sg.suggester || session.players[0])).map((p) => <option key={p}>{p}</option>)}
                </select>
                {sg.disprover !== NOBODY && (
                  <>
                    <span className="dim">card shown (if you saw it)</span>
                    <select value={sg.shown} onChange={(e) => setSg({ ...sg, shown: e.target.value })}>
                      <option value={NOT_SEEN}>not seen</option>
                      {suggestCards.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                    </select>
                  </>
                )}
                <button className="primary" style={{ marginLeft: "auto" }} onClick={addSuggestion}>Add</button>
              </div>
            </div>
          ) : (
            <div className="row">
              <select value={fact.player || session.players[0]} onChange={(e) => setFact({ ...fact, player: e.target.value })}>
                {session.players.map((p) => <option key={p}>{p}</option>)}
              </select>
              <select value={fact.has ? "holds" : "lacks"} onChange={(e) => setFact({ ...fact, has: e.target.value === "holds" })}>
                <option value="holds">holds</option>
                <option value="lacks">lacks</option>
              </select>
              <select value={fact.card || ed.suspects[0]} onChange={(e) => setFact({ ...fact, card: e.target.value })}>
                {cardGroups.map(([groupName, cards]) => (
                  <optgroup key={groupName} label={groupName}>
                    {cards.map((c) => <option key={c} value={c}>{label(c)}</option>)}
                  </optgroup>
                ))}
              </select>
              <button className="primary" style={{ marginLeft: "auto" }} onClick={addFact}>Add</button>
            </div>
          )}
        </div>

        <div className="panel">
          <h3>Observations ({session.observations.length})</h3>
          {session.observations.length === 0 && <div className="dim">Nothing yet — add each suggestion you see at the table.</div>}
          <div className="obs-list">
            {session.observations.map((ob, i) => (
              <div className="row obs" key={i}>
                <span className="dim mono" style={{ width: 18 }}>{i + 1}</span>
                <span style={{ flex: 1 }}>{observationLabel(ob, renames)}</span>
                <button title="remove" onClick={() => removeObservation(i)}>✕</button>
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={exportSession}>Export JSON</button>
            <label className="pill" style={{ cursor: "pointer" }}>
              Import<input type="file" accept="application/json" style={{ display: "none" }} onChange={(e) => e.target.files && importSession(e.target.files[0])} />
            </label>
            <button onClick={reset} style={{ marginLeft: "auto" }}>Reset</button>
          </div>
        </div>
      </div>

      <div className="grid" style={{ alignContent: "start" }}>
        <div className="panel">
          <h3>Probabilities {sol.exact ? "" : "(estimated — large table)"}</h3>
          {!report.ok ? (
            <div>
              <div className="bad">Fix the session first:</div>
              {report.errors.map((e, i) => <div key={i} className="dim">• {e}</div>)}
            </div>
          ) : (
            <div className="scroll-x" ref={probRef}><table className="prob-table">
              <thead>
                <tr>
                  <th />
                  <th>Env</th>
                  {report.players.map((p) => <th key={p} className={p === report.me ? "accent" : ""} title={p}>{p}</th>)}
                </tr>
              </thead>
              <tbody>
                {cardGroups.map(([groupName, cards]) => (
                  [
                    <tr key={groupName} className="group"><td colSpan={2 + report.players.length}><span>{groupName}</span></td></tr>,
                    ...cards.map((card) => {
                      const env = report.conflicts.length ? 0 : sol.cards[card] ?? 0;
                      const hp = report.holders[card] ?? {};
                      return (
                        <tr key={card}>
                          <td className="name" title={card}>{label(card)}{session.faceup.includes(card) ? " ◇" : ""}</td>
                          <td className="p env" style={{ background: heat(env) }}>{pct(env)}</td>
                          {report.players.map((p) => (
                            <td key={p} className="p" style={{ background: hp[p] && hp[p] >= 0.9995 ? "rgba(63,122,90,0.55)" : undefined }}>
                              {hp[p] && hp[p] >= 0.9995 ? "✔" : pct(hp[p])}
                            </td>
                          ))}
                        </tr>
                      );
                    }),
                  ]
                ))}
              </tbody>
            </table></div>
          )}
          {report.ok && probOverflow && (
            <div className="dim swipe-hint">⇄ swipe the grid sideways — the card column stays put</div>
          )}
        </div>
      </div>

      <div className="grid" style={{ alignContent: "start" }}>
        <div className="panel">
          <h3>Candidate solutions</h3>
          {!report.consistent && report.ok ? (
            <div className="bad">No consistent solution — one of your entries must be wrong.</div>
          ) : (
            <>
              <div className="dim" style={{ marginBottom: 6 }}>{sol.n_possible} remaining{sol.exact ? "" : " (propagation + sampling)"}</div>
              {sol.combos.slice(0, 8).map((c) => (
                <div className="row" key={`${c.suspect}|${c.weapon}|${c.room}`} style={{ gap: 6 }}>
                  <span className="mono dim" style={{ width: 48, textAlign: "right" }}>{(c.p * 100).toFixed(1)}%</span>
                  <div className="bar"><div style={{ width: `${Math.max(2, c.p * 100)}%` }} /></div>
                  <span style={{ flex: 1 }}>{label(c.suspect)} / {label(c.weapon)} / {label(c.room)}</span>
                </div>
              ))}
            </>
          )}
        </div>
        <div className="panel coachbox">
          <h3>Guide</h3>
          {report.guide.advice.map((line, i) => (
            <div key={i} className={i === 0 ? "lead" : ""}>{line}</div>
          ))}
          {report.deductions.length > 0 && (
            <>
              <div className="subhead">Hard deductions (provable facts)</div>
              {report.deductions.slice(0, 10).map((d, i) => <div key={i}>• {d}</div>)}
            </>
          )}
          {report.guide.suggestions.length > 0 && (
            <>
              <div className="subhead">Best suggestions to make next</div>
              {report.guide.suggestions.map((s, i) => (
                <div key={i}>• {label(s.suspect)} + {label(s.weapon)} in the {label(s.room)} <span className="dim">(score {s.score.toFixed(2)})</span></div>
              ))}
            </>
          )}
          {Object.keys(report.threat.opponents).length > 0 && (
            <>
              <div className="subhead">Opponent threat</div>
              {Object.entries(report.threat.opponents).map(([p, d]) => (
                <div key={p}>• {p}: ~{d.n_possible} candidates left, p(win next) {d.p_win_next_turn.toFixed(2)}{d.unrefuted ? " — unrefuted suggestion!" : ""}</div>
              ))}
            </>
          )}
          <div className="dim" style={{ marginTop: 10, fontSize: 11 }}>
            Computed locally in your browser with an exact assignment-counting solver (sampled on Large tables) — a port of the Python engine in clue/tools.
          </div>
        </div>
      </div>
    </div>
  );
}

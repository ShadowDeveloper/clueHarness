import { useEffect, useMemo, useState } from "react";
import type { Action, GameState, PendingRequest } from "../api/types";

export type Mode = "idle" | "main" | "move" | "suggest" | "accuse" | "card";

interface Props {
  state: GameState;
  request: PendingRequest | null;
  busy?: boolean;
  onSubmit: (body: { action?: Action; card?: string }) => Promise<void>;
  onPickFromBoard?: (setter: ((target: string) => void) | null, highlights: string[]) => void;
}

const isRoom = (pos: string) => !/^\d+,\d+$/.test(pos);

/**
 * Guided action flow mirroring the TUI: main menu -> move picker (rooms first) / suggest & accuse step pickers
 * (suspect -> weapon [-> room]) / card-to-show picker. Only legal choices are ever offered.
 */
export default function ActionPanel({ state, request, busy, onSubmit, onPickFromBoard }: Props) {
  const [mode, setMode] = useState<Mode>("idle");
  const [build, setBuild] = useState<{ suspect?: string; weapon?: string; room?: string }>({});
  const [pick, setPick] = useState<string | null>(null);
  const legal = request?.legal ?? [];
  const types = useMemo(() => new Set(legal.map((a) => a.type)), [legal]);

  const initialMode = (): Mode => {
    if (!request) return "idle";
    if (request.kind === "card") return "card";
    const t = new Set(request.legal.map((a) => a.type));
    if (t.has("move") && !t.has("roll") && !t.has("suggest") && !t.has("end_turn")) return "move";
    return "main";
  };
  // reset the flow whenever a new request arrives (keyed by id so React's batching cannot leave a stale mode)
  const [seenId, setSeenId] = useState<number | null>(null);
  const curId = request ? request.request_id : null;
  if (curId !== seenId) {
    setSeenId(curId);
    setMode(initialMode());
    setBuild({});
    setPick(null);
  }

  const moves = legal.filter((a) => a.type === "move");
  useEffect(() => {
    if (!onPickFromBoard) return;
    if (mode === "move") onPickFromBoard((t) => submit({ type: "move", to: t }), moves.map((a) => a.to!));
    else onPickFromBoard(null, []);
    return () => onPickFromBoard(null, []);
  }, [mode, request?.request_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // hotkeys (same letters as the TUI)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.ctrlKey || e.metaKey || e.altKey) return;
      if (mode === "main") {
        if (e.key === "r" && types.has("roll")) submit({ type: "roll" });
        if (e.key === "p" && types.has("passage")) submit(legal.find((a) => a.type === "passage")!);
        if (e.key === "s" && types.has("suggest")) setMode("suggest");
        if (e.key === "a" && types.has("accuse")) setMode("accuse");
        if (e.key === "e" && types.has("end_turn")) submit({ type: "end_turn" });
      } else if (e.key === "Escape") back();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const submit = async (a: Action) => { await onSubmit({ action: a }); };
  const back = () => {
    if (mode === "move" && !(types.has("move") && !types.has("roll") && !types.has("end_turn"))) setMode("main");
    else if (mode === "suggest" || mode === "accuse") {
      if (build.weapon) setBuild({ suspect: build.suspect });
      else if (build.suspect) setBuild({});
      else setMode("main");
    }
    setPick(null);
  };

  if (!request) {
    if (state.finished) return <div className="action panel"><div className="banner">Game over — {state.winner ? <b>{state.winner} wins</b> : "no winner"}.</div></div>;
    const acting = state.turn.acting;
    return <div className="action panel"><div className="banner dim">{acting ? `${acting} is ${state.turn.phase === "disprove" ? "choosing a card to show" : "thinking"}…` : "…"}</div></div>;
  }

  const you = state.you!;
  const tag = (c: string) => (you.hand.includes(c) ? "(your card)" : state.notebook?.known_holder[c] ? `(seen — ${state.notebook.known_holder[c]} has it)` : state.cards.faceup.includes(c) ? "(face-up)" : "");

  if (mode === "card") {
    const ps = request.pending_suggestion!;
    return (
      <div className="action panel">
        <div className="banner">{ps.suggester} suggested <b>{ps.suspect}</b> with the <b>{ps.weapon}</b> in the <b>{ps.room}</b>.<br />You hold more than one of these — choose which card to show {ps.suggester} <span className="dim">(only they will see it)</span>:</div>
        <div className="choices">{request.cards.map((c) => <button key={c} className={pick === c ? "sel" : ""} disabled={busy} onClick={() => setPick(c)}>{c}</button>)}</div>
        <div className="row" style={{ marginTop: 8 }}><button className="primary" disabled={!pick || busy} onClick={() => pick && onSubmit({ card: pick })}>Show {pick ?? "…"}</button></div>
      </div>
    );
  }

  if (mode === "move") {
    const rooms = moves.filter((a) => isRoom(a.to!));
    const cells = moves.filter((a) => !isRoom(a.to!));
    return (
      <div className="action panel">
        <div className="banner">You rolled <b>{request.roll ?? state.turn.roll}</b>. Where do you want to go? <span className="dim">(click the board or pick below)</span></div>
        <div className="choices">
          {rooms.map((a) => <button key={a.to} className={pick === a.to ? "sel" : ""} onClick={() => setPick(a.to!)}>Enter the {a.to}<span className="tag">you can suggest there</span></button>)}
          {cells.map((a) => <button key={a.to} className={pick === a.to ? "sel" : ""} onClick={() => setPick(a.to!)}>square {a.to}</button>)}
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <button className="primary" disabled={!pick || busy} onClick={() => pick && submit({ type: "move", to: pick })}>Confirm</button>
          {types.has("end_turn") && <button onClick={() => submit({ type: "end_turn" })}>Stay (end turn)</button>}
        </div>
      </div>
    );
  }

  if (mode === "suggest" || mode === "accuse") {
    const step = !build.suspect ? "suspect" : !build.weapon ? "weapon" : mode === "accuse" && !build.room ? "room" : "done";
    const opts = step === "suspect" ? state.cards.suspects : step === "weapon" ? state.cards.weapons : step === "room" ? state.cards.rooms : [];
    const n = mode === "accuse" ? 3 : 2;
    const idx = step === "suspect" ? 1 : step === "weapon" ? 2 : 3;
    const room = mode === "suggest" ? you.position : build.room;
    const done = step === "done";
    const final: Action = { type: mode, suspect: build.suspect, weapon: build.weapon, room };
    return (
      <div className="action panel">
        <div className="banner">
          {mode === "accuse" ? <span className="bad"><b>Accusation</b> — wrong and you are out. </span> : <>Suggest in the <b>{you.position}</b>: </>}
          {done ? <>{build.suspect} · {build.weapon} · {room}</> : <>Step {idx} of {n}: choose the {step}{build.suspect ? ` — ${build.suspect}` : ""}{build.weapon ? ` · ${build.weapon}` : ""}</>}
        </div>
        {!done && <div className="choices">{opts.map((c) => <button key={c} onClick={() => setBuild({ ...build, [step]: c })}>{c}<span className="tag">{tag(c)}</span></button>)}</div>}
        <div className="row" style={{ marginTop: 8 }}>
          {done && <button className={mode === "accuse" ? "danger" : "primary"} disabled={busy} onClick={() => submit(final)}>{mode === "accuse" ? "Accuse!" : "Suggest"}</button>}
          <button onClick={back}>Back <kbd>Esc</kbd></button>
        </div>
      </div>
    );
  }

  // main menu
  const lines: string[] = [];
  if (types.has("roll")) lines.push("Roll the dice and move");
  if (types.has("passage")) lines.push(`Take the secret passage to the ${legal.find((a) => a.type === "passage")!.to}`);
  if (types.has("suggest")) lines.push(`Suggest here in the ${you.position}` + (types.has("roll") ? " (you were brought here — no need to move)" : ""));
  if (types.has("move") && !types.has("roll")) lines.push("Choose where to move");
  return (
    <div className="action panel">
      <div className="banner"><b>It's your turn.</b> <span className="dim">{lines.join(" · ")}</span></div>
      <div className="row">
        {types.has("roll") && <button className="primary" disabled={busy} onClick={() => submit({ type: "roll" })}>Roll <kbd>r</kbd></button>}
        {types.has("passage") && <button disabled={busy} onClick={() => submit(legal.find((a) => a.type === "passage")!)}>Passage <kbd>p</kbd></button>}
        {types.has("move") && <button disabled={busy} onClick={() => setMode("move")}>Move</button>}
        {types.has("suggest") && <button className="primary" disabled={busy} onClick={() => setMode("suggest")}>Suggest <kbd>s</kbd></button>}
        {types.has("accuse") && <button className="danger" disabled={busy} onClick={() => setMode("accuse")}>Accuse <kbd>a</kbd></button>}
        {types.has("end_turn") && <button disabled={busy} onClick={() => submit({ type: "end_turn" })}>End turn <kbd>e</kbd></button>}
      </div>
    </div>
  );
}

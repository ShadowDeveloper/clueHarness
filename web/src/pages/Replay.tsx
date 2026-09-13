import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Board as Geometry, ReplayFrames, ReplayInfo } from "../api/types";
import Board from "../components/Board";

export default function Replay() {
  const [files, setFiles] = useState<{ name: string; size: number; redacted: boolean }[]>([]);
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [info, setInfo] = useState<ReplayInfo | null>(null);
  const [viewer, setViewer] = useState<string>("");
  const [data, setData] = useState<ReplayFrames | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(0.8);
  const [err, setErr] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api.listReplays().then(setFiles).catch((e) => setErr(String(e))); }, []);
  const edition = info?.edition ?? "classic";
  useEffect(() => { api.board(edition).then(setGeo); }, [edition]);
  const open = async (name: string) => {
    setErr(null);
    try { const i = await api.openReplay(name); setInfo(i); const v = i.viewers[0] ?? ""; setViewer(v); setData(await api.replayFrames(i.id, v || undefined)); setIdx(0); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };
  useEffect(() => { if (info) api.replayFrames(info.id, viewer || undefined).then(setData).catch((e) => setErr(String(e))); }, [viewer]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!playing || !data) return;
    if (idx >= data.frames.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setIdx((i) => Math.min(i + 1, data.frames.length - 1)), speed * 1000);
    return () => clearTimeout(t);
  }, [playing, idx, data, speed]);
  useEffect(() => { const el = logRef.current?.querySelector(".sel"); el?.scrollIntoView({ block: "nearest" }); }, [idx]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (!data || e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const n = data.frames.length - 1;
      if (e.key === "ArrowRight" || e.key === "n") setIdx((i) => Math.min(n, i + 1));
      if (e.key === "ArrowLeft" || e.key === "b") setIdx((i) => Math.max(0, i - 1));
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.key === "g") setIdx(0);
      if (e.key === "G") setIdx(n);
      if (e.key === "+" || e.key === "=") setSpeed((s) => Math.max(0.1, s - 0.2));
      if (e.key === "-") setSpeed((s) => Math.min(5, s + 0.2));
      if (e.key === "v" && info) { const vs = info.viewers; setViewer(vs[(vs.indexOf(viewer) + 1) % vs.length]); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const f = data?.frames[idx];
  const players = data?.info.players ?? [];
  return (
    <div className="page grid replay-grid">
      <div className="grid">
        <div className="panel">
          <h3>Replay files</h3>
          <div className="row">
            <select value={info?.name ?? ""} onChange={(e) => e.target.value && open(e.target.value)} style={{ flex: 1 }}>
              <option value="">choose…</option>
              {files.map((r) => <option key={r.name} value={r.name}>{r.name}{r.redacted ? " (redacted)" : ""}</option>)}
            </select>
            {info && <label>view as <select value={viewer} onChange={(e) => setViewer(e.target.value)}>{info.viewers.map((v) => <option key={v} value={v}>{v === "__omni__" ? "omniscient" : v}</option>)}</select> <kbd>v</kbd></label>}
          </div>
          {err && <div className="bad">{err}</div>}
        </div>
        {geo && f && data && <div className="panel"><Board geo={geo} tokens={f.tokens} weapons={f.weapons} /></div>}
      </div>
      {data && f && (
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="panel row">
            <button onClick={() => setIdx(0)}>⏮ <kbd>g</kbd></button>
            <button onClick={() => setIdx(Math.max(0, idx - 1))}>◀ <kbd>←</kbd></button>
            <button className="primary" onClick={() => setPlaying(!playing)}>{playing ? "⏸" : "▶"} <kbd>space</kbd></button>
            <button onClick={() => setIdx(Math.min(data.frames.length - 1, idx + 1))}>▶| <kbd>→</kbd></button>
            <button onClick={() => setIdx(data.frames.length - 1)}>⏭ <kbd>G</kbd></button>
            <input type="range" min={0} max={data.frames.length - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} style={{ flex: 1 }} />
            <span className="mono">{idx}/{data.frames.length - 1}</span>
            <span className="dim">speed {speed.toFixed(1)}s <kbd>+</kbd><kbd>-</kbd></span>
          </div>
          <div className="panel"><b>{f.text}</b>{f.eliminated.length > 0 && <span className="dim"> · eliminated: {f.eliminated.join(", ")}</span>}</div>
          <div className="panel row" style={{ fontSize: 12 }}>
            {players.map((p) => <span key={p.id} className="pill">{p.id} {data.seat[p.id]}{data.hands[p.id] ? <span className="ok"> · {data.hands[p.id].join(", ")}</span> : null}</span>)}
            {data.solution.length > 0 && <span className="pill hot">envelope: {data.solution.join(" · ")}</span>}
          </div>
          <div className="panel" style={{ maxHeight: 420, overflow: "auto" }} ref={logRef}>
            <h3>Events {viewer === "__omni__" ? "(un-redacted)" : viewer ? `(as ${viewer})` : "(public)"}</h3>
            <div className="log">{data.frames.map((fr, i) => <div key={i} className={`line ${i === idx ? "sel accent" : ""} ${fr.event?.type === "disproved" && fr.event && "card" in fr.event ? "private" : ""}`} onClick={() => setIdx(i)} style={{ cursor: "pointer" }}><span className="dim mono">{String(fr.event?.turn ?? 0).padStart(3, " ")} </span>{fr.text}</div>)}</div>
          </div>
          {data.private_records.length > 0 && (
            <div className="panel" style={{ maxHeight: 200, overflow: "auto" }}>
              <h3>Private reasoning records ({data.private_records.length})</h3>
              <div className="log mono" style={{ fontSize: 11 }}>{data.private_records.slice(0, 300).map((r, i) => <div key={i} className="line">{String(r.player)} · {String(r.kind)} · {String(r.summary ?? r.tool ?? "")}</div>)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

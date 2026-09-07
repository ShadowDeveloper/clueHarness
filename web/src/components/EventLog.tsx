import { useEffect, useRef } from "react";
import type { GameEvent } from "../api/types";

export default function EventLog({ events, me }: { events: GameEvent[]; me?: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight; }, [events.length]);
  return (
    <div className="log" ref={ref} aria-live="polite" aria-label="game log">
      {events.map((e) => (
        <div key={e.seq} className={`line ${e.player === me ? "mine" : ""} ${e.type === "disproved" && "card" in e ? "private" : ""} ${e.type === "accuse" || e.type === "game_over" ? "accuse" : ""}`}>
          <span className="dim mono">{String(e.turn).padStart(3, " ")} </span>{e.text}
        </div>
      ))}
    </div>
  );
}

import { useEffect, useRef } from "react";
import type { GameEvent } from "../api/types";

export default function EventLog({ events, me }: { events: GameEvent[]; me?: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight; }, [events.length]);
  return (
    <div className="log" ref={ref} aria-live="polite" aria-label="game log">
      {events.map((e) => {
        // same colouring as the TUI log
        const t = e.type;
        const cls = t === "accuse" || t === "game_over" || t === "eliminated" ? "accuse" : t === "no_one_disproved" ? "unref" : t === "turn_start" ? "turn" : t === "disproved" && "card" in e ? "private" : t === "suggest" ? "bold" : "";
        const text = t === "turn_start" && me && e.player === me ? "━━━ YOUR TURN ━━━" : e.text;
        return <div key={e.seq} className={`line ${cls}`}>{text}</div>;
      })}
    </div>
  );
}

import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import Analyze from "./pages/Analyze";
import Game from "./pages/Game";
import Lobby from "./pages/Lobby";
import Replay from "./pages/Replay";
import Tournaments from "./pages/Tournaments";

// Static build (GitHub Pages): no backend, so only the client-side Analyst is served.
const STATIC = import.meta.env.VITE_STATIC === "1";

export default function App() {
  return (
    <>
      <nav className="nav">
        <span className="brand">Clue</span>
        {!STATIC && <NavLink to="/" end>Play</NavLink>}
        <NavLink to="/analyze">Analyst</NavLink>
        {!STATIC && <NavLink to="/replays">Replays</NavLink>}
        {!STATIC && <NavLink to="/tournaments">Tournaments</NavLink>}
        {STATIC ? (
          <a href="https://github.com/ShadowDeveloper/clueHarness" target="_blank" rel="noreferrer" className="dim" style={{ marginLeft: "auto" }}>GitHub</a>
        ) : (
          <a href="/api/docs" target="_blank" rel="noreferrer" className="dim" style={{ marginLeft: "auto" }}>API</a>
        )}
      </nav>
      <Routes>
        <Route path="/analyze" element={<Analyze />} />
        {STATIC ? (
          <>
            <Route path="/" element={<Navigate to="/analyze" replace />} />
            <Route path="*" element={<Navigate to="/analyze" replace />} />
          </>
        ) : (
          <>
            <Route path="/" element={<Lobby />} />
            <Route path="/game/:id" element={<Game />} />
            <Route path="/replays" element={<Replay />} />
            <Route path="/tournaments" element={<Tournaments />} />
            <Route path="/tournaments/:id" element={<Tournaments />} />
          </>
        )}
      </Routes>
    </>
  );
}

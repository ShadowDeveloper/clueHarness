import { NavLink, Route, Routes } from "react-router-dom";
import Game from "./pages/Game";
import Lobby from "./pages/Lobby";
import Replay from "./pages/Replay";
import Tournaments from "./pages/Tournaments";

export default function App() {
  return (
    <>
      <nav className="nav">
        <span className="brand">CLUE harness</span>
        <NavLink to="/" end>Play</NavLink>
        <NavLink to="/replays">Replays</NavLink>
        <NavLink to="/tournaments">Tournaments</NavLink>
        <a href="/api/docs" target="_blank" rel="noreferrer" className="dim" style={{ marginLeft: "auto" }}>API</a>
      </nav>
      <Routes>
        <Route path="/" element={<Lobby />} />
        <Route path="/game/:id" element={<Game />} />
        <Route path="/replays" element={<Replay />} />
        <Route path="/tournaments" element={<Tournaments />} />
        <Route path="/tournaments/:id" element={<Tournaments />} />
      </Routes>
    </>
  );
}

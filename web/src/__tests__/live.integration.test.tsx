/**
 * Integration: real pages against a running `clue web` server (CLUE_WEB_URL, default http://localhost:8000).
 * Skipped when the server is not reachable. Uses jsdom + node fetch + the `ws` WebSocket implementation.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import WS from "ws";
import Game from "../pages/Game";
import Lobby from "../pages/Lobby";
import Tournaments from "../pages/Tournaments";

const BASE = process.env.CLUE_WEB_URL ?? "http://localhost:8000";
let up = false;
try { up = (await fetch(`${BASE}/api/health`)).ok; } catch { up = false; }

const realFetch = globalThis.fetch;
beforeAll(() => {
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => realFetch(typeof input === "string" && input.startsWith("/") ? BASE + input : input, init)) as typeof fetch;
  Object.defineProperty(window, "location", { value: new URL(BASE), writable: true });
  (globalThis as unknown as { WebSocket: unknown }).WebSocket = WS;
});

describe.skipIf(!up)("live server", () => {
  it("lobby creates a game and the Game page plays a human turn over the wire", async () => {
    const created = await realFetch(`${BASE}/api/games`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ players_arg: "human,baseline:expert,baseline", seed: 5, delay: 0 }) }).then((r) => r.json());
    localStorage.setItem(`clue:${created.id}`, JSON.stringify({ owner: created.owner_token, spectator: created.spectator_token }));
    render(<MemoryRouter initialEntries={[`/game/${created.id}?k=${created.owner_token}`]}><Routes><Route path="/game/:id" element={<Game />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/It's your turn/)).toBeInTheDocument(), { timeout: 15000 });
    expect(screen.getByText(/Your hand:/)).toBeInTheDocument();
    expect(document.querySelectorAll("svg.board .token").length).toBe(6); // all six suspect tokens are always on the board
    await act(async () => { fireEvent.keyDown(document.body, { key: "r" }); });
    await waitFor(() => expect(screen.getByText(/You rolled/)).toBeInTheDocument(), { timeout: 10000 });
    const hl = document.querySelectorAll("svg.board .hl");
    expect(hl.length).toBeGreaterThan(0);
    await act(async () => { hl[0].dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await waitFor(() => expect(document.querySelectorAll(".log .line").length).toBeGreaterThan(2), { timeout: 10000 });
    // coach
    await act(async () => { fireEvent.keyDown(document.body, { key: "h" }); });
    await waitFor(() => expect(document.querySelector(".coach")).not.toBeNull());
    // quit saves
    await act(async () => { fireEvent.keyDown(document.body, { key: "q" }); });
    await waitFor(() => expect(screen.getByText(/saved to/)).toBeInTheDocument(), { timeout: 10000 });
  }, 60000);

  it("lobby lists saves and games", async () => {
    render(<MemoryRouter><Lobby /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Resume a saved game/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Games on this server/)).toBeInTheDocument());
    await waitFor(() => expect(document.querySelectorAll(".panel .row .mono").length).toBeGreaterThan(0), { timeout: 10000 }); // at least one game/save listed
  }, 20000);

  it("tournament page starts a run and shows the table", async () => {
    render(<MemoryRouter initialEntries={["/tournaments"]}><Routes><Route path="/tournaments" element={<Tournaments />} /><Route path="/tournaments/:id" element={<Tournaments />} /></Routes></MemoryRouter>);
    const input = await screen.findByDisplayValue(/baseline:expert/);
    fireEvent.change(input, { target: { value: "baseline:expert,baseline,baseline" } });
    fireEvent.change(screen.getByDisplayValue("20"), { target: { value: "4" } });
    await act(async () => { fireEvent.click(screen.getByText("Start")); });
    await waitFor(() => expect(screen.getByText("finished")).toBeInTheDocument(), { timeout: 120000 });
    expect(document.querySelectorAll("table.tbl tbody tr").length).toBe(2);
    expect(document.querySelector("svg[aria-label='candidate count curves']")).not.toBeNull();
  }, 150000);
});

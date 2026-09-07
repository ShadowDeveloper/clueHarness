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
    expect(document.querySelector(".tline")!.textContent).toMatch(/your cards:/);
    expect(document.querySelectorAll(".tboard .token").length).toBe(6); // all six suspect tokens are always on the board
    await act(async () => { fireEvent.keyDown(document.body, { key: "r" }); });
    await waitFor(() => expect(screen.getByText(/You rolled/)).toBeInTheDocument(), { timeout: 10000 });
    const hl = document.querySelectorAll(".tboard .hl");
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

  it("remote seats: host sees invite links and a seat page waits, then gets its hand once everyone joined", async () => {
    const created = await realFetch(`${BASE}/api/games`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ players_arg: "human,human,human,baseline", seed: 8, delay: 0, remote: true }) }).then((r) => r.json());
    expect(created.remote).toBe(true);
    const k2 = created.seat_tokens.P2 as string, k3 = created.seat_tokens.P3 as string;
    // host tab (owner token; nothing in localStorage yet -> role derives from the token)
    localStorage.setItem(`clue:${created.id}`, JSON.stringify({ owner: created.owner_token, spectator: created.spectator_token, seats: created.seat_tokens }));
    const host = render(<MemoryRouter initialEntries={[`/game/${created.id}?k=${created.owner_token}`]}><Routes><Route path="/game/:id" element={<Game />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Waiting for players/)).toBeInTheDocument(), { timeout: 15000 });
    await waitFor(() => expect(document.querySelectorAll(".remote-lobby input").length).toBe(3), { timeout: 10000 });
    const links = [...document.querySelectorAll<HTMLInputElement>(".remote-lobby input")].map((i) => i.value);
    expect(links[1]).toContain(`/game/${created.id}?k=${k2}`);
    expect(links[2]).toContain(`/game/${created.id}?k=${k3}`);
    expect(document.querySelector(".remote-lobby")!.textContent).toContain("still to join: P2, P3"); // the host IS seat P1
    host.unmount();
    // player 2's "browser": no stored tokens, only the invite link
    localStorage.clear();
    render(<MemoryRouter initialEntries={[`/game/${created.id}?k=${k2}`]}><Routes><Route path="/game/:id" element={<Game />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Waiting for players/)).toBeInTheDocument(), { timeout: 15000 });
    expect(screen.getByText(/Keep this tab open/)).toBeInTheDocument();
    expect(document.querySelector(".remote-lobby")!.textContent).toContain("still to join: P3");
    expect(document.querySelectorAll(".remote-lobby input").length).toBe(0); // seats never see invite tokens
    // P3 joins from another browser (raw socket) -> lobby closes for P2, hand visible, and it is P1's turn
    const ws1 = new WS(`${BASE.replace("http", "ws")}/ws/games/${created.id}?k=${k3}`);
    await new Promise<void>((res) => ws1.once("open", () => res()));
    await waitFor(() => expect(screen.queryByText(/Waiting for players/)).toBeNull(), { timeout: 15000 });
    await waitFor(() => expect(document.querySelector(".tline")!.textContent).toMatch(/your cards:/), { timeout: 15000 });
    expect(document.querySelector(".action")!.textContent).toMatch(/P1 is thinking/);
    expect(JSON.parse(localStorage.getItem(`clue:${created.id}`)!).seat).toBe(k2); // seat link remembered for the lobby list
    ws1.close();
    await realFetch(`${BASE}/api/games/${created.id}?k=${created.owner_token}`, { method: "DELETE" });
  }, 60000);
});

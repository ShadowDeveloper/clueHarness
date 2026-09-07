import { fireEvent, render, screen } from "@testing-library/react";
import ActionPanel from "../components/ActionPanel";
import { cardReq, moveReq, rollReq, roomReq, state } from "./fixtures";

test("main menu offers only legal buttons and r rolls", async () => {
  const onSubmit = vi.fn(async () => {});
  render(<ActionPanel state={state} request={rollReq} onSubmit={onSubmit} />);
  expect(screen.getByText(/It's your turn/)).toBeInTheDocument();
  expect(screen.queryByText(/Suggest/)).toBeNull();
  fireEvent.keyDown(window, { key: "r" });
  expect(onSubmit).toHaveBeenCalledWith({ action: { type: "roll" } });
});

test("move picker lists rooms first and confirms the selection", async () => {
  const onSubmit = vi.fn(async () => {});
  const onPick = vi.fn();
  render(<ActionPanel state={state} request={moveReq} onSubmit={onSubmit} onPickFromBoard={onPick} />);
  expect(screen.getByText(/You rolled/)).toBeInTheDocument();
  expect(onPick).toHaveBeenCalledWith(expect.any(Function), ["Lounge", "19,7", "20,8"]);
  const buttons = screen.getAllByRole("button").map((b) => b.textContent);
  expect(buttons[0]).toMatch(/Enter the Lounge/);
  fireEvent.click(screen.getByText(/Enter the Lounge/));
  fireEvent.click(screen.getByText("Confirm"));
  expect(onSubmit).toHaveBeenCalledWith({ action: { type: "move", to: "Lounge" } });
});

test("suggest is a 2-step picker with tags, accuse is 3 steps and Esc goes back", async () => {
  const onSubmit = vi.fn(async () => {});
  const inRoom = { ...state, you: { ...state.you!, position: "Hall" } };
  render(<ActionPanel state={inRoom} request={roomReq} onSubmit={onSubmit} />);
  fireEvent.keyDown(window, { key: "s" });
  expect(screen.getByText(/Step 1 of 2/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Prof. Plum"));
  expect(screen.getByText(/Step 2 of 2/)).toBeInTheDocument();
  expect(screen.getByText("(your card)")).toBeInTheDocument(); // Knife tagged
  fireEvent.click(screen.getByText("Rope"));
  expect(screen.getByText(/Prof. Plum · Rope · Hall/)).toBeInTheDocument();
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.getByText(/Step 2 of 2/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Rope"));
  fireEvent.click(screen.getByText("Suggest"));
  expect(onSubmit).toHaveBeenCalledWith({ action: { type: "suggest", suspect: "Prof. Plum", weapon: "Rope", room: "Hall" } });
});

test("accuse flow needs a room and shows a warning", () => {
  const onSubmit = vi.fn(async () => {});
  render(<ActionPanel state={state} request={rollReq} onSubmit={onSubmit} />);
  fireEvent.keyDown(window, { key: "a" });
  expect(screen.getByText(/Accusation/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Mr. Green"));
  fireEvent.click(screen.getByText("Wrench"));
  expect(screen.getByText(/Step 3 of 3/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Study"));
  fireEvent.click(screen.getByText("Accuse!"));
  expect(onSubmit).toHaveBeenCalledWith({ action: { type: "accuse", suspect: "Mr. Green", weapon: "Wrench", room: "Study" } });
});

test("card picker only offers the disproving cards", () => {
  const onSubmit = vi.fn(async () => {});
  render(<ActionPanel state={state} request={cardReq} onSubmit={onSubmit} />);
  expect(screen.getByText(/choose which card to show P2/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Hall" }));
  fireEvent.click(screen.getByText(/Show Hall/));
  expect(onSubmit).toHaveBeenCalledWith({ card: "Hall" });
});

test("no request: shows who is thinking", () => {
  render(<ActionPanel state={{ ...state, turn: { ...state.turn, acting: "P2" } }} request={null} onSubmit={async () => {}} />);
  expect(screen.getByText(/P2 is thinking/)).toBeInTheDocument();
});

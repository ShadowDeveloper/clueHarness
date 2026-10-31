// Analyst page: client-side solver wiring, card entry, observations, and the guide panel.
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Analyze from "../pages/Analyze";

describe("Analyze page", () => {
  beforeEach(() => localStorage.clear());

  it("computes probabilities from entered cards and observations", () => {
    render(<Analyze />);
    // enter my hand
    for (const card of ["Miss Scarlet", "Rope", "Hall", "Study", "Candlestick"]) {
      fireEvent.click(screen.getByRole("button", { name: card }));
    }
    expect(screen.getByText(/Your hand \(5\)/)).toBeInTheDocument();
    // my cards are certainly mine in the probability grid
    expect(screen.getAllByText("✔").length).toBeGreaterThanOrEqual(5);
    // guide reflects a fresh game
    expect(screen.getByText(/candidate solutions remain/)).toBeInTheDocument();
    expect(screen.getByText(/Too early to accuse/)).toBeInTheDocument();

    // add a suggestion: P2 suggested Col. Mustard / Dagger / Lounge, P3 disproved (card not seen)
    const combos = screen.getAllByRole("combobox");
    // [0]=edition [1]=you-are [2]=suggester [3]=suspect [4]=weapon [5]=room [6]=disprover
    fireEvent.change(combos[2], { target: { value: "P2" } });
    fireEvent.change(combos[3], { target: { value: "Col. Mustard" } });
    fireEvent.change(combos[4], { target: { value: "Dagger" } });
    fireEvent.change(combos[5], { target: { value: "Lounge" } });
    fireEvent.change(combos[6], { target: { value: "P3" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("Observations (1)")).toBeInTheDocument();
    expect(screen.getByText(/P2: Col. Mustard \/ Dagger \/ Lounge -> P3 disproved/)).toBeInTheDocument();

    // a fact: P4 holds Mrs. Peacock
    fireEvent.click(screen.getByRole("button", { name: "Add fact" }));
    const factCombos = screen.getAllByRole("combobox");
    fireEvent.change(factCombos[2], { target: { value: "P4" } });
    fireEvent.change(factCombos[4], { target: { value: "Mrs. Peacock" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("Observations (2)")).toBeInTheDocument();
    expect(screen.getByText(/fact: P4 holds Mrs. Peacock/)).toBeInTheDocument();

    // deleting the fact restores the previous state
    fireEvent.click(screen.getAllByTitle("remove")[1]);
    expect(screen.getByText("Observations (1)")).toBeInTheDocument();
  });

  it("validates the session and supports reset", () => {
    render(<Analyze />);
    const players = screen.getByPlaceholderText("Me, Alice, Bob, Cara");
    fireEvent.change(players, { target: { value: "A, B" } });
    fireEvent.keyDown(players, { key: "Enter" });
    expect(screen.getByText(/Fix the session first/)).toBeInTheDocument();
    expect(screen.getByText(/needs 3\.\.6 players/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.queryByText(/Fix the session first/)).not.toBeInTheDocument();
  });

  it("persists the session in localStorage", () => {
    const first = render(<Analyze />);
    fireEvent.click(screen.getByRole("button", { name: "Wrench" }));
    first.unmount();
    render(<Analyze />);
    expect(screen.getByText(/Your hand \(1\)/)).toBeInTheDocument();
  });
});

describe("Analyze page face-up cards on touch", () => {
  beforeEach(() => localStorage.clear());

  it("tap-cycles a chip none -> hand -> face-up -> none when face-up mode is on", () => {
    render(<Analyze />);
    fireEvent.click(screen.getByRole("checkbox")); // enable face-up cards
    expect(screen.getByText(/tap again for face-up/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rope" })); // none -> hand
    expect(screen.getByText(/Your hand \(1\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rope" })); // hand -> face-up
    expect(screen.getByText(/Your hand \(0\)/)).toBeInTheDocument();
    expect(screen.getByTitle("Rope (face-up)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rope" })); // face-up -> none
    expect(screen.queryByTitle("Rope (face-up)")).not.toBeInTheDocument();
  });

  it("shift-click still jumps straight to face-up, and unchecking clears them", () => {
    render(<Analyze />);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Hall" }), { shiftKey: true });
    expect(screen.getByTitle("Hall (face-up)")).toBeInTheDocument();
    expect(screen.getByText(/Your hand \(0\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox")); // disable face-up mode -> clears face-up cards
    expect(screen.queryByTitle("Hall (face-up)")).not.toBeInTheDocument();
  });
});

describe("Analyze page card renames", () => {
  beforeEach(() => localStorage.clear());

  it("renames cards everywhere and supports restoring", () => {
    render(<Analyze />);
    fireEvent.click(screen.getByRole("button", { name: "Lead Pipe" }));
    // open the rename editor and rename Lead Pipe
    fireEvent.click(screen.getByRole("button", { name: /Rename cards \(0\)/ }));
    const combos = screen.getAllByRole("combobox");
    const renameSelect = combos[2]; // [0]=edition [1]=you-are [2]=rename picker (suggestion selects come later)
    fireEvent.change(renameSelect, { target: { value: "Lead Pipe" } });
    const input = screen.getByPlaceholderText("name on your cards");
    fireEvent.change(input, { target: { value: "Bleirohr" } });
    fireEvent.click(screen.getByRole("button", { name: "Set" }));
    // chip, probability grid, and selects now use the label; canonical name is gone from the grid
    expect(screen.getByRole("button", { name: "Bleirohr" })).toBeInTheDocument();
    expect(screen.getByText(/Rename cards \(1\)/)).toBeInTheDocument();
    for (const el of screen.getAllByTitle("Lead Pipe")) expect(el).toHaveTextContent("Bleirohr");
    // observation labels use it too
    const all = screen.getAllByRole("combobox");
    fireEvent.change(all[all.length - 5], { target: { value: "P2" } }); // suggester
    fireEvent.change(all[all.length - 3], { target: { value: "Lead Pipe" } }); // weapon
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText(/P2: Miss Scarlet \/ Bleirohr \/ Hall/)).toBeInTheDocument();
    // restore the canonical name
    fireEvent.click(screen.getByTitle("restore standard name"));
    expect(screen.getByText(/Rename cards \(0\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lead Pipe" })).toBeInTheDocument();
  });

  it("rejects duplicate labels via validation", () => {
    render(<Analyze />);
    fireEvent.click(screen.getByRole("button", { name: /Rename cards \(0\)/ }));
    const combos = screen.getAllByRole("combobox");
    const input = screen.getByPlaceholderText("name on your cards");
    fireEvent.change(combos[2], { target: { value: "Rope" } });
    fireEvent.change(input, { target: { value: "Knife" } });
    fireEvent.click(screen.getByRole("button", { name: "Set" }));
    fireEvent.change(combos[2], { target: { value: "Dagger" } });
    fireEvent.change(input, { target: { value: "knife" } });
    fireEvent.click(screen.getByRole("button", { name: "Set" }));
    expect(screen.getByText(/Fix the session first/)).toBeInTheDocument();
    expect(screen.getByText(/two cards share the label 'knife'/)).toBeInTheDocument();
  });
});

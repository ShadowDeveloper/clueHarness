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

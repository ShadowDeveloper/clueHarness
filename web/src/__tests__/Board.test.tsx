import { render } from "@testing-library/react";
import Board, { parseSq } from "../components/Board";
import type { Board as Geometry } from "../api/types";

const geo: Geometry = { rows: 25, cols: 24, rooms: { Lounge: [[19, 17], [19, 18], [20, 17], [20, 18]] }, corridor: [[24, 7], [19, 7], [20, 8]], doors: [{ cell: [19, 7], rooms: ["Lounge"] }], passages: {}, cellar: [10, 16, 9, 14], starts: { "0": [24, 7] } };

test("parseSq", () => {
  expect(parseSq("24,7")).toEqual([24, 7]);
  expect(parseSq("Lounge")).toBeNull();
});

test("highlights are clickable and fire onPick with room or square", () => {
  const onPick = vi.fn();
  const { container } = render(<Board geo={geo} tokens={{ "Miss Scarlet": "24,7", "Prof. Plum": "Lounge" }} weapons={{ Rope: "Lounge" }} highlights={["Lounge", "19,7"]} onPick={onPick} />);
  expect(container.querySelectorAll(".cell.hl")).toHaveLength(1);
  expect(container.querySelector(".cell.hl")!.textContent).toBe("◆");
  (container.querySelector(".cell.hl") as HTMLElement).click();
  expect(onPick).toHaveBeenCalledWith("19,7");
  (container.querySelector(".room.hl") as HTMLElement).click();
  expect(onPick).toHaveBeenCalledWith("Lounge");
  expect(container.querySelectorAll(".tboard .token")).toHaveLength(2); // Scarlet on 24,7 + Plum inside the Lounge
  expect(container.querySelector(".tboard .weapon")!.textContent).toBe("r"); // rope initial bottom-left of the room
  expect(container.querySelector(".tboard .door")!.textContent).not.toBe("·");
  expect(container.textContent).toContain("Miss Scarlet"); // legend
});

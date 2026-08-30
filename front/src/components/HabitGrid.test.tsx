import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import HabitGrid from "./HabitGrid";

const twoHabits = [
  { id: 1, name: "Exercise", is_archived: false },
  { id: 2, name: "Coding", is_archived: false },
];

describe("HabitGrid", () => {
  it("opens a day from the date cell instead of toggling a dot", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();

    render(
      <HabitGrid
        habits={twoHabits}
        days={[21]}
        month="2026-07"
        lookup={{}}
        selectedDate={null}
        onSelectDate={onSelectDate}
      />,
    );

    expect(
      screen.queryByRole("button", {
        name: "Exercise on 2026-07-21: not completed",
      }),
    ).toBeNull();

    await user.click(
      screen.getByRole("button", { name: "2026-07-21, 0 of 2 complete" }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
  });

  it("keeps archived history selectable from the date cell", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();

    render(
      <HabitGrid
        habits={[{ id: 1, name: "Read", is_archived: true }]}
        days={[21]}
        month="2026-07"
        lookup={{ "1-2026-07-21": true }}
        selectedDate={null}
        onSelectDate={onSelectDate}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "2026-07-21, 1 of 1 complete" }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
  });

  it("opens history from a habit name", async () => {
    const user = userEvent.setup();
    const onSelectHabit = vi.fn();

    render(
      <HabitGrid
        habits={[{ id: 1, name: "Read", is_archived: false }]}
        days={[21]}
        month="2026-07"
        lookup={{}}
        selectedDate={null}
        onSelectDate={vi.fn()}
        onSelectHabit={onSelectHabit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open Read history" }));
    expect(onSelectHabit).toHaveBeenCalledWith(1);
  });

  it("gives neighboring habits different legend marks", () => {
    const { container } = render(
      <HabitGrid
        habits={twoHabits}
        days={[21]}
        month="2026-07"
        lookup={{}}
        selectedDate={null}
        onSelectDate={vi.fn()}
      />,
    );

    const marks = container.querySelectorAll("li span:first-child");
    expect(marks[0].className).toContain("habit-mark-1");
    expect(marks[1].className).toContain("habit-mark-2");
    expect(marks[0].className).not.toBe(marks[1].className);
  });
});

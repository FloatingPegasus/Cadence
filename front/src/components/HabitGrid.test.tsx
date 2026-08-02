import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import HabitGrid from "./HabitGrid";

describe("HabitGrid", () => {
  it("exposes habit cells as keyboard-operable pressed buttons", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    const onSelectDate = vi.fn();

    render(
      <HabitGrid
        habits={[{ id: 1, name: "Read", is_archived: false }]}
        days={[21]}
        month="2026-07"
        lookup={{}}
        onToggle={onToggle}
        selectedDate={null}
        onSelectDate={onSelectDate}
      />,
    );

    const cell = screen.getByRole("button", {
      name: "Read on 2026-07-21: not completed",
    });
    expect(cell.getAttribute("aria-pressed")).toBe("false");

    cell.focus();
    await user.keyboard("{Enter}");

    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
    expect(onToggle).toHaveBeenCalledWith(1, "2026-07-21", "1");
  });

  it("keeps archived history selectable without changing it", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    const onSelectDate = vi.fn();

    render(
      <HabitGrid
        habits={[{ id: 1, name: "Read", is_archived: true }]}
        days={[21]}
        month="2026-07"
        lookup={{ "1-2026-07-21": true }}
        onToggle={onToggle}
        selectedDate={null}
        onSelectDate={onSelectDate}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Read on 2026-07-21: completed, archived",
      }),
    );

    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("opens continuity from a discipline name", async () => {
    const user = userEvent.setup();
    const onSelectHabit = vi.fn();

    render(
      <HabitGrid
        habits={[{ id: 1, name: "Read", is_archived: false }]}
        days={[21]}
        month="2026-07"
        lookup={{}}
        onToggle={vi.fn()}
        selectedDate={null}
        onSelectDate={vi.fn()}
        onSelectHabit={onSelectHabit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open Read continuity" }));
    expect(onSelectHabit).toHaveBeenCalledWith(1);
  });
});

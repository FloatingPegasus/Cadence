import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DayHabitsDialog from "./DayHabitsDialog";

const habits = [
  { id: 1, name: "Exercise", is_archived: false },
  { id: 2, name: "Coding", is_archived: false },
];

describe("DayHabitsDialog", () => {
  it("toggles a habit immediately", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    render(
      <DayHabitsDialog
        date="2026-07-21"
        habits={habits}
        lookup={{}}
        onToggle={onToggle}
        onOpenDay={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    screen.getByRole("dialog", { name: /21/ });
    await user.click(
      screen.getByRole("checkbox", {
        name: "Mark Exercise complete for 2026-07-21",
      }),
    );
    expect(onToggle).toHaveBeenCalledWith(1, "2026-07-21", "1");
  });

  it("closes on Escape and opens the day", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onOpenDay = vi.fn();

    render(
      <DayHabitsDialog
        date="2026-07-21"
        habits={habits}
        lookup={{}}
        onToggle={vi.fn()}
        onOpenDay={onOpenDay}
        onClose={onClose}
      />,
    );

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Open day" }));
    expect(onOpenDay).toHaveBeenCalledOnce();
  });

  it("marks two habits with different colors", () => {
    const { container } = render(
      <DayHabitsDialog
        date="2026-07-21"
        habits={habits}
        lookup={{}}
        onToggle={vi.fn()}
        onOpenDay={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const marks = container.querySelectorAll("label span span:first-child");
    expect(marks[0].className).toContain("habit-mark-1");
    expect(marks[1].className).toContain("habit-mark-2");
  });
});

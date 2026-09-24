import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DashboardNav from "./DashboardNav";

describe("DashboardNav", () => {
  it("shows the five daily workspaces", () => {
    render(<DashboardNav view="today" onChange={vi.fn()} />);
    for (const name of ["Today", "Tasks", "Hours", "Focus", "History"]) {
      screen.getByRole("button", { name });
    }
    expect(screen.queryByRole("button", { name: "Calendar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Settings" })).toBeNull();
  });

  it("moves through the workspaces by keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DashboardNav view="today" onChange={onChange} />);

    const today = screen.getByRole("button", { name: "Today" });
    today.focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("tasks");
    await user.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith("continuity");
    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("today");
  });
});

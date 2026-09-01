import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DashboardNav from "./DashboardNav";

describe("DashboardNav", () => {
  it("shows all seven workspaces", () => {
    render(<DashboardNav view="today" onChange={vi.fn()} />);
    for (const name of [
      "Today",
      "Tasks",
      "Hours",
      "Focus",
      "Calendar",
      "History",
      "Settings",
    ]) {
      screen.getByRole("button", { name });
    }
  });

  it("moves through the seven workspaces by keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(
      <DashboardNav view="today" onChange={onChange} />,
    );

    const today = screen.getByRole("button", { name: "Today" });
    today.focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("tasks");

    rerender(<DashboardNav view="settings" onChange={onChange} />);
    const settings = screen.getByRole("button", { name: "Settings" });
    settings.focus();
    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("today");
  });
});

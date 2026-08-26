import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DashboardNav from "./DashboardNav";

describe("DashboardNav", () => {
  it("moves through the six workspaces by keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(
      <DashboardNav view="today" onChange={onChange} />,
    );

    const today = screen.getByRole("button", { name: "Today" });
    today.focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("hours");

    rerender(<DashboardNav view="settings" onChange={onChange} />);
    const settings = screen.getByRole("button", { name: "Settings" });
    settings.focus();
    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("today");
  });
});

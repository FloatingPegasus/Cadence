import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ContinuityExplorer from "./ContinuityExplorer";

vi.mock("./ContextHub", () => ({
  default: () => <div>Context panel</div>,
}));
vi.mock("./ContinuitySearch", () => ({
  default: () => <div>Search panel</div>,
}));
vi.mock("./WeeklyContinuity", () => ({
  default: () => <div>Week panel</div>,
}));
vi.mock("./MonthlyContinuity", () => ({
  default: () => <div>Month panel</div>,
}));
vi.mock("./ContinuityPatterns", () => ({
  default: () => <div>Patterns panel</div>,
}));

describe("ContinuityExplorer", () => {
  it("moves between views with arrow, Home, and End keys", async () => {
    const user = userEvent.setup();

    render(
      <ContinuityExplorer
        contexts={[
          {
            id: 1,
            name: "Cadence",
            kind: "project",
            is_archived: false,
          },
        ]}
        anchorDate="2026-07-21"
        selectedDate={null}
        onSelectDate={vi.fn()}
        refreshKey={0}
      />,
    );

    screen.getByText("Week panel");
    const weekTab = screen.getByRole("tab", { name: "Week" });
    expect(weekTab.getAttribute("aria-selected")).toBe("true");
    weekTab.focus();

    await user.keyboard("{ArrowRight}");
    screen.getByText("Month panel");

    await user.keyboard("{End}");
    screen.getByText("Patterns panel");

    await user.keyboard("{Home}");
    screen.getByText("Context panel");
  });
});

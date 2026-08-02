import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  beforeEach(() => {
    vi.restoreAllMocks();
  });

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

    const contextsTab = screen.getByRole("tab", { name: "Contexts" });
    contextsTab.focus();
    expect(screen.getByText("Context panel")).toBeTruthy();

    await user.keyboard("{ArrowRight}");
    const searchTab = screen.getByRole("tab", { name: "Search" });
    expect(document.activeElement).toBe(searchTab);
    expect(searchTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Search panel")).toBeTruthy();

    await user.keyboard("{End}");
    expect(screen.getByText("Patterns panel")).toBeTruthy();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByText("Month panel")).toBeTruthy();

    await user.keyboard("{Home}");
    expect(screen.getByText("Context panel")).toBeTruthy();
  });
});

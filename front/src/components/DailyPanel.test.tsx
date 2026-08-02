import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DailyPanel from "./DailyPanel";

vi.mock("./daily/ReentryCard", () => ({ default: () => <div>Re-entry</div> }));
vi.mock("./daily/DailyCaptureCard", () => ({ default: () => <div>Capture form</div> }));
vi.mock("./daily/QuickThreadCard", () => ({ default: () => <div>Quick thread</div> }));
vi.mock("./daily/CarryForwardCard", () => ({ default: () => <div>Carry forward</div> }));
vi.mock("./daily/DailySummaryCard", () => ({ default: () => <div>Summary editor</div> }));
vi.mock("./daily/DayClosureCard", () => ({ default: () => <div>Day closure</div> }));

describe("DailyPanel", () => {
  it("reveals one daily task group at a time", async () => {
    const user = userEvent.setup();
    render(
      <DailyPanel
        date="2026-07-24"
        contexts={[]}
        refreshKey={0}
        onSelectDate={vi.fn()}
        onChanged={vi.fn()}
      />,
    );

    expect(screen.getByText("Capture form")).toBeTruthy();
    expect(screen.queryByText("Quick thread")).toBeNull();

    await user.click(screen.getByRole("button", { name: "threads" }));
    expect(screen.getByText("Quick thread")).toBeTruthy();
    expect(screen.queryByText("Capture form")).toBeNull();

    await user.click(screen.getByRole("button", { name: "reflect" }));
    expect(screen.getByText("Summary editor")).toBeTruthy();
    expect(screen.queryByText("Quick thread")).toBeNull();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { generateSummary } from "../api";
import DailyPanel from "./DailyPanel";

vi.mock("./daily/ReentryCard", () => ({ default: () => <div>Re-entry</div> }));
vi.mock("./daily/DailyCaptureCard", () => ({
  default: ({ onChanged }: { onChanged: (hasSource?: boolean) => void }) => (
    <>
      <div>Capture form</div>
      <button type="button" onClick={() => onChanged(true)}>
        Save note
      </button>
    </>
  ),
}));
vi.mock("./daily/DailyHabitsCard", () => ({ default: () => <div>Daily practices</div> }));
vi.mock("./daily/QuickThreadCard", () => ({ default: () => <div>Today&apos;s log</div> }));
vi.mock("./daily/CarryForwardCard", () => ({ default: () => <div>Follow-ups</div> }));
vi.mock("./daily/DailySummaryCard", () => ({ default: () => <div>Summary editor</div> }));
vi.mock("./daily/DayClosureCard", () => ({ default: () => <div>Day closure</div> }));
vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { ai_processing_consent: true } }),
}));
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, generateSummary: vi.fn() };
});

describe("DailyPanel", () => {
  it("reveals one daily task group at a time", async () => {
    const user = userEvent.setup();
    render(
      <DailyPanel
        date="2026-07-24"
        habits={[]}
        contexts={[]}
        refreshKey={0}
        onSelectDate={vi.fn()}
        onChanged={vi.fn()}
        onHabitsChanged={vi.fn()}
      />,
    );

    screen.getByText("Capture form");
    screen.getByText("Today's log");

    await user.click(screen.getByRole("button", { name: "Follow-ups" }));
    expect(screen.getAllByText("Follow-ups")).toHaveLength(2);
    expect(screen.queryByText("Capture form")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Summary" }));
    screen.getByText("Summary editor");
    expect(screen.queryByText("Today's log")).toBeNull();
  });

  it("updates the summary after a new note is saved", async () => {
    const user = userEvent.setup();
    vi.mocked(generateSummary).mockResolvedValue(
      {} as Awaited<ReturnType<typeof generateSummary>>,
    );

    render(
      <DailyPanel
        date="2026-07-24"
        habits={[]}
        contexts={[]}
        refreshKey={0}
        onSelectDate={vi.fn()}
        onChanged={vi.fn()}
        onHabitsChanged={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save note" }));
    expect(generateSummary).toHaveBeenCalledWith("2026-07-24");
    await screen.findByText("Summary updated");
  });
});

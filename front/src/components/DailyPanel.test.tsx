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
vi.mock("./daily/DailyHabitsCard", () => ({ default: () => <div>Habits</div> }));
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
  it("shows habits, notes, and the daily review together", () => {
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

    screen.getByText("Habits");
    screen.getByText("Capture form");
    screen.getByText("Follow-ups");
    screen.getByText("Summary editor");
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
  });
});

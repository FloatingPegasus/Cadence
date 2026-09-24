import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { generateSummary } from "../api";
import { todayAsLocalDate } from "../time";
import DailyPanel from "./DailyPanel";

vi.mock("./daily/ReentryCard", () => ({ default: () => <div>Re-entry</div> }));
vi.mock("./daily/LogNote", () => ({ default: () => <div>Log note</div> }));
vi.mock("./daily/TodayList", () => ({ default: () => <div>Today list</div> }));
vi.mock("./daily/CloseDayCard", () => ({
  default: ({
    onChanged,
    children,
  }: {
    onChanged: (hasSource?: boolean) => void;
    children?: ReactNode;
  }) => (
    <>
      <div>Close form</div>
      <button type="button" onClick={() => onChanged(true)}>
        Save note
      </button>
      {children}
    </>
  ),
}));
vi.mock("./daily/CarryForwardCard", () => ({ default: () => <div>Follow-ups</div> }));
vi.mock("./daily/DailySummaryCard", () => ({ default: () => <div>Summary editor</div> }));
const auth = vi.hoisted(() => ({
  user: { ai_processing_consent: true, day_ends_at: 0 },
  aiEnabled: true,
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, generateSummary: vi.fn() };
});

function renderPanel(date: string) {
  render(
    <DailyPanel
      date={date}
      contexts={[]}
      refreshKey={0}
      onSelectDate={vi.fn()}
      onStartFocus={vi.fn()}
      onChanged={vi.fn()}
      onHabitsChanged={vi.fn()}
      onTasksChanged={vi.fn()}
    />,
  );
}

function at(hour: number) {
  vi.useFakeTimers({ toFake: ["Date"] });
  const now = new Date();
  now.setHours(hour, 15, 0, 0);
  vi.setSystemTime(now);
}

describe("DailyPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    auth.user.day_ends_at = 0;
  });

  it("shows the log note by day and switches to closing quietly", async () => {
    at(15);
    const user = userEvent.setup();
    renderPanel(todayAsLocalDate());

    screen.getByText("Log note");
    screen.getByText("Today list");
    expect(screen.queryByText("Close form")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Close the day" }));
    screen.getByText("Close form");
    screen.getByText("Summary editor");
    screen.getByText("Follow-ups");
    await user.click(screen.getByRole("button", { name: "Log something" }));
    screen.getByText("Log note");
  });

  it("closes the day from 6 PM", () => {
    at(19);
    renderPanel(todayAsLocalDate());
    screen.getByText("Close form");
    screen.getByRole("button", { name: "Log something" });
  });

  it("keeps closing mode until the day ends in the small hours", () => {
    at(2);
    auth.user.day_ends_at = 4;
    renderPanel(todayAsLocalDate());
    screen.getByText("Close form");
  });

  it("opens past days in close mode without the switch", () => {
    at(10);
    renderPanel("2026-07-24");
    screen.getByText("Close form");
    expect(screen.queryByText("Log note")).toBeNull();
    expect(screen.queryByRole("button", { name: "Log something" })).toBeNull();
  });

  it("updates the summary after a closing note is saved", async () => {
    const user = userEvent.setup();
    vi.mocked(generateSummary).mockResolvedValue(
      {} as Awaited<ReturnType<typeof generateSummary>>,
    );
    renderPanel("2026-07-24");

    await user.click(screen.getByRole("button", { name: "Save note" }));
    expect(generateSummary).toHaveBeenCalledWith("2026-07-24");
  });
});

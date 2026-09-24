import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  beginDay,
  fetchContexts,
  fetchHabits,
  fetchMonthData,
  fetchTasks,
} from "../api";
import { authStub } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import { todayAsLocalDate } from "../time";
import DashboardPage from "./DashboardPage";

vi.mock("../api", () => ({
  beginDay: vi.fn(),
  fetchContexts: vi.fn(),
  fetchHabits: vi.fn(),
  fetchMonthData: vi.fn(),
  fetchTasks: vi.fn(),
  toggleHabit: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("./Header", () => ({
  default: ({ onOpenSettings }: { onOpenSettings: () => void }) => (
    <button type="button" onClick={onOpenSettings}>
      Settings
    </button>
  ),
}));
vi.mock("./DailyPanel", () => ({
  default: ({ onStartFocus }: { onStartFocus: () => void }) => (
    <div>
      Daily workspace
      <button type="button" onClick={onStartFocus}>
        Start focus
      </button>
    </div>
  ),
}));
vi.mock("./HabitGrid", () => ({ default: () => <div>Habit calendar</div> }));
vi.mock("./MonthNav", () => ({ default: () => <div>Month navigation</div> }));
vi.mock("./DisciplineContinuity", () => ({ default: () => <div>Discipline detail</div> }));
vi.mock("./ContinuityExplorer", () => ({
  default: ({ calendar }: { calendar?: ReactNode }) => (
    <div>
      Continuity workspace
      {calendar}
    </div>
  ),
}));
vi.mock("./SettingsPanel", () => ({ default: () => <div>Settings workspace</div> }));
vi.mock("./HoursPage", () => ({ default: () => <div>Hours workspace</div> }));
vi.mock("./TasksPage", () => ({ default: () => <div>Tasks workspace</div> }));
vi.mock("./FocusPage", () => ({
  default: ({ startSignal }: { startSignal: number }) => (
    <div>Focus workspace {startSignal}</div>
  ),
}));

describe("DashboardPage progressive disclosure", () => {
  beforeEach(() => {
    vi.mocked(beginDay).mockResolvedValue({ closed: [] });
  });

  it("loads one workspace at a time and defers calendar data", async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue(authStub());
    vi.mocked(fetchHabits).mockResolvedValue([
      { id: 1, name: "Read", is_archived: false },
    ]);
    vi.mocked(fetchContexts).mockResolvedValue([]);
    vi.mocked(fetchMonthData).mockResolvedValue({
      days: [1],
      month: "2026-07",
      habits: [{ id: 1, name: "Read", is_archived: false }],
      lookup: {},
    });
    vi.mocked(fetchTasks).mockResolvedValue([]);

    render(<DashboardPage />);
    screen.getByText("Daily workspace");
    expect(beginDay).toHaveBeenCalledWith(todayAsLocalDate());
    expect(
      screen.getByText("Tasks workspace").closest("[hidden]"),
    ).not.toBeNull();
    expect(screen.queryByText("Continuity workspace")).toBeNull();
    expect(screen.queryByText("Settings workspace")).toBeNull();
    expect(fetchMonthData).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Hours" }));
    expect(
      screen.getByText("Hours workspace").closest("[hidden]"),
    ).toBeNull();
    expect(
      screen.getByText("Daily workspace").closest("[hidden]"),
    ).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "History" }));
    await waitFor(() => expect(fetchMonthData).toHaveBeenCalledOnce());
    await screen.findByText("Habit calendar");
    expect(
      screen.getByText("Daily workspace").closest("[hidden]"),
    ).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(
      screen.getByText("Settings workspace").closest("[hidden]"),
    ).toBeNull();
    expect(
      screen.getByText("Habit calendar").closest("[hidden]"),
    ).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(
      screen.getByText("Daily workspace").closest("[hidden]"),
    ).toBeNull();
  });

  it("shows Today and Focus without a session", async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue(authStub({ user: null }));

    render(<DashboardPage />);
    screen.getByText("Daily workspace");
    expect(fetchHabits).not.toHaveBeenCalled();
    expect(beginDay).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Focus" }));
    expect(
      screen.getByText("Focus workspace 0").closest("[hidden]"),
    ).toBeNull();

    await user.click(screen.getByRole("button", { name: "History" }));
    expect(fetchMonthData).not.toHaveBeenCalled();
    screen.getByRole("heading", { name: "History" });
    screen.getByText("Nothing here yet.");
  });

  it("titles Home with the date and starts focus from it", async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue(authStub({ user: null }));

    render(<DashboardPage />);
    const title = new Date().toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    screen.getByRole("heading", { name: title });
    expect(screen.queryByRole("button", { name: "Back to today" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Start focus" }));
    expect(
      screen.getByText("Focus workspace 1").closest("[hidden]"),
    ).toBeNull();
  });
});

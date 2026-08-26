import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  fetchContexts,
  fetchHabits,
  fetchMonthData,
} from "../api";
import { useAuth } from "../contexts/AuthContext";
import DashboardPage from "./DashboardPage";

vi.mock("../api", () => ({
  fetchContexts: vi.fn(),
  fetchHabits: vi.fn(),
  fetchMonthData: vi.fn(),
  toggleHabit: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("./Header", () => ({ default: () => <div>Header</div> }));
vi.mock("./DailyPanel", () => ({ default: () => <div>Daily workspace</div> }));
vi.mock("./RecentDays", () => ({ default: () => <div>Recent days</div> }));
vi.mock("./HabitGrid", () => ({ default: () => <div>Habit calendar</div> }));
vi.mock("./MonthNav", () => ({ default: () => <div>Month navigation</div> }));
vi.mock("./DisciplineContinuity", () => ({ default: () => <div>Discipline detail</div> }));
vi.mock("./ContinuityExplorer", () => ({ default: () => <div>Continuity workspace</div> }));
vi.mock("./SettingsPanel", () => ({ default: () => <div>Settings workspace</div> }));
vi.mock("./HoursPage", () => ({ default: () => <div>Hours workspace</div> }));
vi.mock("./FocusPage", () => ({ default: () => <div>Focus workspace</div> }));

describe("DashboardPage progressive disclosure", () => {
  it("loads one workspace at a time and defers calendar data", async () => {
    const user = userEvent.setup();
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        username: "alpha",
        email: "alpha@example.com",
        is_verified: true,
        is_developer: false,
        ai_processing_consent: false,
        ai_redaction_enabled: true,
      },
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      resendVerification: vi.fn(),
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });
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

    render(<DashboardPage />);
    screen.getByText("Daily workspace");
    expect(screen.queryByText("Continuity workspace")).toBeNull();
    expect(screen.queryByText("Settings workspace")).toBeNull();
    expect(fetchMonthData).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Hours" }));
    screen.getByText("Hours workspace");
    expect(screen.queryByText("Daily workspace")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Calendar" }));
    await waitFor(() => expect(fetchMonthData).toHaveBeenCalledOnce());
    await screen.findByText("Habit calendar");
    expect(screen.queryByText("Daily workspace")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Settings" }));
    screen.getByText("Settings workspace");
    expect(screen.queryByText("Habit calendar")).toBeNull();
  });
});

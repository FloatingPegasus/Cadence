import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  fetchWeeklyContinuity,
  type WeeklyContinuity as WeeklyContinuityData,
} from "../api";
import WeeklyContinuity from "./WeeklyContinuity";

vi.mock("../api", () => ({
  fetchWeeklyContinuity: vi.fn(),
}));
vi.mock("./WeeklyReflectionCard", () => ({
  default: () => <div>Reflection editor</div>,
}));
vi.mock("./WeeklyReflectionHistory", () => ({
  default: ({
    onSelectWeek,
  }: {
    onSelectWeek: (weekStart: string) => void;
  }) => (
    <button type="button" onClick={() => onSelectWeek("2026-07-13")}>
      Open historical week
    </button>
  ),
}));

function week(weekStart: string, weekEnd: string): WeeklyContinuityData {
  return {
    week_start: weekStart,
    week_end: weekEnd,
    totals: {
      active_days: 0,
      closed_days: 0,
      habit_completions: 0,
    },
    days: [],
    open_threads: [],
  };
}

describe("WeeklyContinuity", () => {
  it("browses a historical week without selecting a day", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchWeeklyContinuity)
      .mockResolvedValueOnce(week("2026-07-20", "2026-07-26"))
      .mockResolvedValueOnce(week("2026-07-13", "2026-07-19"));

    render(
      <WeeklyContinuity
        anchorDate="2026-07-23"
        selectedDate={null}
        onSelectDate={vi.fn()}
        refreshKey={0}
        embedded
      />,
    );

    await screen.findByText("Jul 20 – Jul 26");
    await user.click(
      screen.getByRole("button", { name: "Open historical week" }),
    );

    await waitFor(() =>
      expect(fetchWeeklyContinuity).toHaveBeenLastCalledWith("2026-07-13"),
    );
    expect(await screen.findByText("Jul 13 – Jul 19")).toBeTruthy();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fetchWeeklyReflectionHistory } from "../api";
import WeeklyReflectionHistory from "./WeeklyReflectionHistory";

vi.mock("../api", () => ({
  fetchWeeklyReflectionHistory: vi.fn(),
}));

describe("WeeklyReflectionHistory", () => {
  it("opens a historical week without selecting a daily trace", async () => {
    const user = userEvent.setup();
    const onSelectWeek = vi.fn();
    vi.mocked(fetchWeeklyReflectionHistory).mockResolvedValue([
      {
        id: 1,
        week_start: "2026-07-13",
        week_end: "2026-07-19",
        excerpt: "Retrieval became easier to navigate.",
        is_user_edited: true,
        model: null,
        updated_at: "2026-07-20T12:00:00",
      },
    ]);

    render(
      <WeeklyReflectionHistory
        currentWeekStart="2026-07-20"
        refreshKey={0}
        onSelectWeek={onSelectWeek}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Open week Jul 13 to Jul 19",
      }),
    );
    expect(onSelectWeek).toHaveBeenCalledWith("2026-07-13");
  });
});

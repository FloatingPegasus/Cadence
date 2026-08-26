import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fetchContextMonthlyContinuity } from "../api";
import ContextMonthlyDetail from "./ContextMonthlyDetail";

vi.mock("../api", () => ({
  fetchContextMonthlyContinuity: vi.fn(),
}));

describe("ContextMonthlyDetail", () => {
  it("supports prior and daily re-entry inside a context month", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();
    vi.mocked(fetchContextMonthlyContinuity).mockResolvedValue({
      context: {
        id: 1,
        name: "Cadence",
        kind: "project",
        is_archived: false,
      },
      month: "2026-07",
      month_start: "2026-07-01",
      month_end: "2026-07-31",
      totals: {
        active_days: 1,
        closed_days: 0,
        habit_completions: 0,
        conversation_entries: 1,
      },
      previous_activity: {
        date: "2026-06-28",
        excerpt: "The prior project context.",
        source: "note",
      },
      weeks: [
        {
          week_start: "2026-07-13",
          week_end: "2026-07-19",
          active_days: 1,
          closed_days: 0,
          habit_completions: 0,
          last_date: "2026-07-18",
          last_trace_preview: "The current project trace.",
        },
      ],
      days: [
        {
          date: "2026-07-18",
          status: "open",
          trace_preview: "The current project trace.",
          trace_source: "note",
          energy_level: null,
          focus_quality: null,
          habit_completions: 0,
          conversation_entries: 1,
        },
      ],
      open_threads: [],
    });

    render(
      <ContextMonthlyDetail
        contextId={1}
        month="2026-07"
        refreshKey={0}
        onSelectDate={onSelectDate}
        onClose={vi.fn()}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Open prior Cadence activity from Jun 28",
      }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-06-28");

    await user.click(
      screen.getByRole("button", {
        name: "Open Cadence note for Jul 18",
      }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-18");
  });
});

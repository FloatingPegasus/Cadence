import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  fetchMonthlyContinuity,
  type MonthlyContinuity as MonthlyContinuityData,
} from "../api";
import MonthlyContinuity from "./MonthlyContinuity";

vi.mock("../api", () => ({
  fetchMonthlyContinuity: vi.fn(),
}));
vi.mock("./ContextMonthlyDetail", () => ({
  default: ({ contextId }: { contextId: number }) => (
    <div>Context detail {contextId}</div>
  ),
}));

function month(
  value: string,
  start: string,
  end: string,
  day?: string,
): MonthlyContinuityData {
  return {
    month: value,
    month_start: start,
    month_end: end,
    totals: {
      active_days: day ? 1 : 0,
      closed_days: 0,
      habit_completions: 0,
      weekly_reflections: 0,
    },
    days: day
      ? [
          {
            date: day,
            status: "open",
            trace_preview: "A meaningful monthly trace.",
            trace_source: "note",
            energy_level: null,
            focus_quality: null,
            checkin_fields: 0,
            habit_completions: 0,
            conversation_entries: 0,
            contexts: [],
          },
        ]
      : [],
    weekly_reflections: [],
    contexts: [],
    open_threads: [],
  };
}

describe("MonthlyContinuity", () => {
  it("opens days and browses months independently", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();
    vi.mocked(fetchMonthlyContinuity)
      .mockResolvedValueOnce(
        month("2026-07", "2026-07-01", "2026-07-31", "2026-07-15"),
      )
      .mockResolvedValueOnce(
        month("2026-06", "2026-06-01", "2026-06-30"),
      );

    render(
      <MonthlyContinuity
        anchorDate="2026-07-23"
        selectedDate={null}
        onSelectDate={onSelectDate}
        refreshKey={0}
        embedded
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Open day for Jul 15",
      }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-15");

    await user.click(
      screen.getByRole("button", { name: "Previous month" }),
    );
    await waitFor(() =>
      expect(fetchMonthlyContinuity).toHaveBeenLastCalledWith("2026-06"),
    );
    await screen.findByText("June 2026");
  });

  it("opens area activity inline", async () => {
    const user = userEvent.setup();
    const data = month("2026-07", "2026-07-01", "2026-07-31");
    data.contexts = [
      {
        id: 1,
        name: "Cadence",
        kind: "project",
        active_days: 3,
        last_date: "2026-07-18",
        last_trace_preview: "The context moved forward.",
      },
    ];
    vi.mocked(fetchMonthlyContinuity).mockResolvedValue(data);

    render(
      <MonthlyContinuity
        anchorDate="2026-07-23"
        selectedDate={null}
        onSelectDate={vi.fn()}
        refreshKey={0}
        embedded
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Open Cadence monthly activity",
      }),
    );
    screen.getByText("Context detail 1");
  });
});

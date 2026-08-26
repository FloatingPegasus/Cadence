import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DisciplineContinuity from "./DisciplineContinuity";
import { fetchDisciplineMonthlyContinuity } from "../api";

vi.mock("../api", () => ({
  fetchDisciplineMonthlyContinuity: vi.fn(),
}));

const fetchContinuity = vi.mocked(fetchDisciplineMonthlyContinuity);

describe("DisciplineContinuity", () => {
  it("shows completion trace and opens its dates", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();
    fetchContinuity.mockResolvedValue({
      discipline: { id: 1, name: "Read", is_archived: false },
      month: "2026-07",
      month_start: "2026-07-01",
      month_end: "2026-07-31",
      totals: { completed_days: 1, linked_trace_days: 1, contexts: 1 },
      previous_completion: { date: "2026-06-28", excerpt: "Earlier trace" },
      days: [{
        date: "2026-07-05",
        status: "open",
        trace_preview: "First reading trace",
        trace_source: "note",
        conversation_entries: 0,
        contexts: [{ id: 2, name: "Cadence", kind: "project" }],
      }],
      contexts: [{ id: 2, name: "Cadence", kind: "project", completed_days: 1 }],
    });

    render(
      <DisciplineContinuity
        disciplineId={1}
        month="2026-07"
        selectedDate={null}
        onSelectDate={onSelectDate}
        refreshKey={0}
        onClose={vi.fn()}
      />,
    );

    await screen.findByText("First reading trace");
    expect(screen.getAllByText("Cadence").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Previous completion/ }));
    await user.click(screen.getByRole("button", { name: /Jul 5/ }));

    expect(onSelectDate).toHaveBeenNthCalledWith(1, "2026-06-28");
    expect(onSelectDate).toHaveBeenNthCalledWith(2, "2026-07-05");
  });
});

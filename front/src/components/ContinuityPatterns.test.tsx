import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { fetchContinuityPatterns } from "../api";
import ContinuityPatterns from "./ContinuityPatterns";

vi.mock("../api", () => ({ fetchContinuityPatterns: vi.fn() }));

describe("ContinuityPatterns", () => {
  it("presents evidence without scoring the user", async () => {
    vi.mocked(fetchContinuityPatterns).mockResolvedValue({
      start_date: "2026-06-01",
      end_date: "2026-07-26",
      weeks: 8,
      totals: { recorded_days: 12, active_weeks: 6 },
      weekly: [{
        week_start: "2026-07-20",
        week_end: "2026-07-26",
        active_days: 3,
        habit_completions: 4,
        average_energy: 3.5,
        average_focus: null,
      }],
      observations: [{
        kind: "rhythm",
        title: "Recorded rhythm",
        body: "Activity appears in 6 of 8 weeks.",
        evidence: { active_weeks: 6 },
      }],
      interpretation: "Patterns describe recorded data only. They are not scores.",
    });

    render(
      <ContinuityPatterns anchorDate="2026-07-24" refreshKey={0} />,
    );

    expect(await screen.findByText("Recorded rhythm")).toBeTruthy();
    expect(screen.getByText(/not scores/)).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
  });
});

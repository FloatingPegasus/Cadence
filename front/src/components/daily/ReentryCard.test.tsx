import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fetchDayReentry } from "../../api";
import ReentryCard from "./ReentryCard";

vi.mock("../../api", () => ({
  fetchDayReentry: vi.fn(),
}));

describe("ReentryCard", () => {
  it("surfaces bounded prior context with direct date re-entry", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();
    vi.mocked(fetchDayReentry).mockResolvedValue({
      date: "2026-07-23",
      previous_trace: {
        date: "2026-07-22",
        source: "summary",
        excerpt: "The migration and interaction tests stabilized.",
      },
      open_threads: [
        {
          id: 1,
          origin_date: "2026-07-22",
          content: "Finish the re-entry view",
        },
      ],
      contexts: [
        {
          id: 1,
          name: "Cadence",
          kind: "project",
          last_activity: {
            date: "2026-07-21",
            source: "note",
            excerpt: "Defined the bounded continuity contract.",
          },
        },
      ],
    });

    render(
      <ReentryCard
        date="2026-07-23"
        refreshKey={0}
        onSelectDate={onSelectDate}
      />,
    );

    expect(
      await screen.findByText(
        "The migration and interaction tests stabilized.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Finish the re-entry view")).toBeTruthy();

    await user.click(
      screen.getByRole("button", {
        name: "Open Cadence context from Jul 21",
      }),
    );
    expect(onSelectDate).toHaveBeenCalledWith("2026-07-21");
  });
});

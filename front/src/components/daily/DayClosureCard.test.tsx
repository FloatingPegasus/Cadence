import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  fetchClosurePreview,
  updateDayStatus,
} from "../../api";
import DayClosureCard from "./DayClosureCard";

vi.mock("../../api", () => ({
  fetchClosurePreview: vi.fn(),
  updateDayStatus: vi.fn(),
}));

describe("DayClosureCard", () => {
  it("allows an empty day to close after a non-blocking review", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    vi.mocked(fetchClosurePreview).mockResolvedValue({
      date: "2026-07-23",
      status: "open",
      capture: {
        has_daily_note: false,
        conversation_entries: 0,
        completed_habits: 0,
        checkin_fields: 0,
      },
      summary: {
        exists: false,
        excerpt: "",
        is_user_edited: false,
      },
      open_thread_count: 0,
      open_threads: [],
    });
    vi.mocked(updateDayStatus).mockResolvedValue({
      id: 1,
      date: "2026-07-23",
      status: "closed",
      daily_note: "",
    });

    render(
      <DayClosureCard
        date="2026-07-23"
        refreshKey={0}
        onChanged={onChanged}
      />,
    );

    const summaryToggle = await screen.findByText("Finish the day");
    const details = summaryToggle.closest("details");
    if (details) details.open = true;
    await user.click(
      await screen.findByRole("button", { name: "Review and finish" }),
    );
    await user.click(screen.getByRole("button", { name: "Finish day" }));

    await waitFor(() =>
      expect(updateDayStatus).toHaveBeenCalledWith(
        "2026-07-23",
        "closed",
      ),
    );
    expect(onChanged).toHaveBeenCalled();
  });
});

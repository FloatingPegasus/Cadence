import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fetchHourLog, upsertHourLog } from "../api";
import HoursPage from "./HoursPage";

vi.mock("../api", () => ({
  fetchHourLog: vi.fn(),
  upsertHourLog: vi.fn(),
}));

describe("HoursPage", () => {
  it("saves an hour when the field is left", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchHourLog).mockResolvedValue(
      Array.from({ length: 24 }, (_, hour) => ({ hour, content: "" })),
    );
    vi.mocked(upsertHourLog).mockResolvedValue({
      hour: 9,
      content: "Deep work",
    });

    render(
      <HoursPage
        date="2026-07-24"
        onSelectDate={vi.fn()}
        onChanged={vi.fn()}
      />,
    );

    const field = await screen.findByLabelText("9 AM");
    await user.type(field, "Deep work");
    await user.tab();

    expect(upsertHourLog).toHaveBeenCalledWith(
      "2026-07-24",
      9,
      "Deep work",
    );
  });
});

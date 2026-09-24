import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { authStub } from "../../authTest";
import { useAuth } from "../../contexts/AuthContext";
import CloseDayCard from "./CloseDayCard";

vi.mock("../../api", () => ({
  fetchCheckin: vi.fn(),
  fetchDay: vi.fn(),
  fetchDayContexts: vi.fn(),
  updateCheckin: vi.fn(),
  updateDay: vi.fn(),
  updateDayContexts: vi.fn(),
  updateDayStatus: vi.fn(),
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

function day(daily_note = "", status = "open") {
  return { id: 1, date: "2026-07-23", status, daily_note };
}

describe("CloseDayCard", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
    vi.mocked(api.fetchDayContexts).mockResolvedValue([]);
    vi.mocked(api.updateDay).mockResolvedValue(day());
    vi.mocked(api.updateCheckin).mockResolvedValue({});
    vi.mocked(api.updateDayContexts).mockResolvedValue([]);
  });

  it("saves cleared check-in fields as explicit null values", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDay).mockResolvedValue(day("Keep the source text."));
    vi.mocked(api.fetchCheckin).mockResolvedValue({
      energy_level: 4,
      emotional_state: "Steady",
      focus_quality: 3,
    });

    render(<CloseDayCard date="2026-07-23" contexts={[]} onChanged={vi.fn()} />);

    const energy = await screen.findByRole("group", { name: "Energy" });
    const selected = within(energy).getByRole("button", { name: "4" });
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    await user.click(selected);
    const more = screen.getByText("More").closest("details");
    if (more) more.open = true;
    await user.clear(screen.getByRole("textbox", { name: "Emotional state" }));
    await user.tab();

    await waitFor(() => {
      expect(vi.mocked(api.updateCheckin).mock.calls.at(-1)?.[1]).toEqual({
        energy_level: null,
        emotional_state: null,
        focus_quality: 3,
      });
    });
  });

  it("sets a score in one tap and saves the remembered line as the day note", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDay).mockResolvedValue(day());
    vi.mocked(api.fetchCheckin).mockResolvedValue({});

    render(<CloseDayCard date="2026-07-23" contexts={[]} onChanged={vi.fn()} />);

    await user.click(
      within(await screen.findByRole("group", { name: "Sleep" })).getByRole(
        "button",
        { name: "5, Restful" },
      ),
    );
    await waitFor(() =>
      expect(vi.mocked(api.updateCheckin).mock.calls.at(-1)?.[1]).toEqual({
        sleep_quality: 5,
      }),
    );

    await user.type(
      screen.getByRole("textbox", { name: "One thing worth remembering" }),
      "Meera said yes to the demo",
    );
    await user.tab();
    await waitFor(() =>
      expect(api.updateDay).toHaveBeenLastCalledWith(
        "2026-07-23",
        "Meera said yes to the demo",
      ),
    );
  });

  it("closes and reopens the day", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    vi.mocked(api.fetchDay).mockResolvedValue(day());
    vi.mocked(api.fetchCheckin).mockResolvedValue({});
    vi.mocked(api.updateDayStatus)
      .mockResolvedValueOnce(day("", "closed"))
      .mockResolvedValueOnce(day("", "open"));

    render(
      <CloseDayCard date="2026-07-23" contexts={[]} onChanged={onChanged} />,
    );

    await user.click(await screen.findByRole("button", { name: "Close" }));
    expect(api.updateDayStatus).toHaveBeenCalledWith("2026-07-23", "closed");
    await screen.findByRole("heading", { name: "Day closed" });
    expect(onChanged).toHaveBeenLastCalledWith(true);

    await user.click(screen.getByRole("button", { name: "Reopen" }));
    expect(api.updateDayStatus).toHaveBeenLastCalledWith("2026-07-23", "open");
    await screen.findByRole("heading", { name: "Close the day" });
  });
});

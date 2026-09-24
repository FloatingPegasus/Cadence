import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { authStub } from "../../authTest";
import { useAuth } from "../../contexts/AuthContext";
import DailyCaptureCard from "./DailyCaptureCard";

vi.mock("../../api", () => ({
  fetchCheckin: vi.fn(),
  fetchDay: vi.fn(),
  fetchDayContexts: vi.fn(),
  updateCheckin: vi.fn(),
  updateDay: vi.fn(),
  updateDayContexts: vi.fn(),
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("hybrid daily capture", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
  });

  it("saves cleared check-in fields as explicit null values", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDay).mockResolvedValue({
      id: 1,
      date: "2026-07-23",
      status: "open",
      daily_note: "Keep the source text.",
    });
    vi.mocked(api.fetchCheckin).mockResolvedValue({
      energy_level: 4,
      emotional_state: "Steady",
      focus_quality: 3,
    });
    vi.mocked(api.fetchDayContexts).mockResolvedValue([]);
    vi.mocked(api.updateDay).mockResolvedValue({
      id: 1,
      date: "2026-07-23",
      status: "open",
      daily_note: "Keep the source text.",
    });
    vi.mocked(api.updateCheckin).mockResolvedValue({});
    vi.mocked(api.updateDayContexts).mockResolvedValue([]);

    render(
      <DailyCaptureCard
        date="2026-07-23"
        contexts={[]}
        onChanged={vi.fn()}
      />,
    );

    const checkinSummary = await screen.findByText("Check-in");
    const checkinDetails = checkinSummary.closest("details");
    if (checkinDetails) checkinDetails.open = true;
    const energy = screen.getByRole("group", { name: "Energy" });
    const selected = within(energy).getByRole("button", { name: "4" });
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    await user.click(selected);
    const extraSummary = screen.getByText("Add more detail");
    const extraDetails = extraSummary.closest("details");
    if (extraDetails) extraDetails.open = true;
    await user.clear(
      screen.getByRole("textbox", { name: "Emotional state" }),
    );
    await user.tab();

    await waitFor(() => {
      const calls = vi.mocked(api.updateCheckin).mock.calls;
      expect(calls.at(-1)?.[1]).toEqual({
        energy_level: null,
        emotional_state: null,
        focus_quality: 3,
      });
    });
  });

  it("sets a check-in score in one tap and saves typed detail on leave", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchDay).mockResolvedValue({
      id: 1,
      date: "2026-07-23",
      status: "open",
      daily_note: "",
    });
    vi.mocked(api.fetchCheckin).mockResolvedValue({});
    vi.mocked(api.fetchDayContexts).mockResolvedValue([]);
    vi.mocked(api.updateDay).mockResolvedValue({
      id: 1,
      date: "2026-07-23",
      status: "open",
      daily_note: "",
    });
    vi.mocked(api.updateCheckin).mockResolvedValue({});
    vi.mocked(api.updateDayContexts).mockResolvedValue([]);
    vi.mocked(api.updateCheckin).mockClear();

    render(
      <DailyCaptureCard
        date="2026-07-23"
        contexts={[]}
        onChanged={vi.fn()}
      />,
    );

    const checkinDetails = (await screen.findByText("Check-in")).closest("details");
    if (checkinDetails) checkinDetails.open = true;
    await user.click(
      within(screen.getByRole("group", { name: "Focus" })).getByRole("button", {
        name: "5, Clear",
      }),
    );
    await waitFor(() =>
      expect(vi.mocked(api.updateCheckin).mock.calls.at(-1)?.[1]).toEqual({
        focus_quality: 5,
      }),
    );

    const extraDetails = screen.getByText("Add more detail").closest("details");
    if (extraDetails) extraDetails.open = true;
    const calls = vi.mocked(api.updateCheckin).mock.calls.length;
    await user.type(
      screen.getByRole("textbox", { name: "Emotional state" }),
      "tired",
    );
    expect(vi.mocked(api.updateCheckin).mock.calls.length).toBe(calls);
    await user.tab();
    await waitFor(() =>
      expect(vi.mocked(api.updateCheckin).mock.calls.length).toBe(calls + 1),
    );
    expect(vi.mocked(api.updateCheckin).mock.calls.at(-1)?.[1]).toEqual({
      focus_quality: 5,
      emotional_state: "tired",
    });
  });
});

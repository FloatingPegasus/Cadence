import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import DailyCaptureCard from "./DailyCaptureCard";
import QuickThreadCard from "./QuickThreadCard";

vi.mock("../../api", () => ({
  addConversationEntry: vi.fn(),
  fetchCheckin: vi.fn(),
  fetchConversation: vi.fn(),
  fetchDay: vi.fn(),
  fetchDayContexts: vi.fn(),
  updateCheckin: vi.fn(),
  updateDay: vi.fn(),
  updateDayContexts: vi.fn(),
}));

describe("hybrid daily capture", () => {
  beforeEach(() => {
    vi.resetAllMocks();
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

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Energy" }),
      "",
    );
    await user.click(screen.getByText("Add more detail"));
    await user.clear(
      screen.getByRole("textbox", { name: "Emotional state" }),
    );
    await user.click(screen.getByRole("button", { name: "Save note" }));

    await waitFor(() =>
      expect(api.updateCheckin).toHaveBeenCalledWith("2026-07-23", {
        energy_level: null,
        emotional_state: null,
        focus_quality: 3,
      }),
    );
  });

  it("uses prompts as guidance without changing the saved entry", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchConversation).mockResolvedValue([]);
    vi.mocked(api.addConversationEntry).mockResolvedValue({
      id: 1,
      role: "user",
      content: "The migration is finally stable.",
      created_at: "2026-07-23T12:00:00",
    });

    render(
      <QuickThreadCard date="2026-07-23" onChanged={vi.fn()} />,
    );

    const prompt = await screen.findByRole("button", {
      name: "What moved forward?",
    });
    await user.click(prompt);

    const input = screen.getByRole("textbox", {
      name: "What moved forward?",
    });
    expect(document.activeElement).toBe(input);
    await user.type(input, "The migration is finally stable.");
    await user.click(screen.getByRole("button", { name: "Log" }));

    await waitFor(() =>
      expect(api.addConversationEntry).toHaveBeenCalledWith(
        "2026-07-23",
        "The migration is finally stable.",
      ),
    );
  });
});

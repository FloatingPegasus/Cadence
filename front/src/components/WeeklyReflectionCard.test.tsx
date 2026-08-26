import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  fetchWeeklyReflection,
  updateWeeklyReflection,
  type WeeklyReflection,
} from "../api";
import WeeklyReflectionCard from "./WeeklyReflectionCard";

vi.mock("../api", () => ({
  fetchWeeklyReflection: vi.fn(),
  generateWeeklyReflection: vi.fn(),
  updateWeeklyReflection: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { ai_processing_consent: true },
  }),
}));

function reflection(isStale: boolean): WeeklyReflection {
  return {
    id: 1,
    week_start: "2026-07-20",
    week_end: "2026-07-26",
    content: "The weekly source became coherent.",
    provider: null,
    model: null,
    prompt_version: "weekly-reflection-v1",
    source_fingerprint: "b".repeat(64),
    is_stale: isStale,
    is_user_edited: true,
    generated_at: null,
    updated_at: "2026-07-23T12:00:00",
  };
}

describe("WeeklyReflectionCard", () => {
  it("supports manual refresh when the weekly source changes", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchWeeklyReflection).mockResolvedValue(reflection(true));
    vi.mocked(updateWeeklyReflection).mockResolvedValue(reflection(false));

    render(
      <WeeklyReflectionCard
        anchorDate="2026-07-23"
        refreshKey={0}
        onChanged={vi.fn()}
      />,
    );

    await screen.findByText(/The week changed after this review/);
    await user.click(
      screen.getByRole("button", { name: "Save review" }),
    );

    await waitFor(() =>
      expect(updateWeeklyReflection).toHaveBeenCalledWith(
        "2026-07-23",
        "The weekly source became coherent.",
      ),
    );
    expect(
      screen.queryByText(/The week changed after this review/),
    ).toBeNull();
  });
});

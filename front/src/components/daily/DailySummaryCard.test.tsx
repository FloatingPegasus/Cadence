import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchSummary,
  updateSummary,
  type DailySummary,
} from "../../api";
import DailySummaryCard from "./DailySummaryCard";

vi.mock("../../api", () => ({
  fetchSummary: vi.fn(),
  generateSummary: vi.fn(),
  updateSummary: vi.fn(),
}));
vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { ai_processing_consent: true },
  }),
}));

function summary(isStale: boolean): DailySummary {
  return {
    id: 1,
    kind: "daily",
    content: "The original summary.",
    provider: null,
    model: null,
    prompt_version: "daily-summary-v1",
    source_fingerprint: "a".repeat(64),
    is_stale: isStale,
    is_user_edited: true,
    generated_at: null,
    updated_at: "2026-07-23T12:00:00",
  };
}

describe("DailySummaryCard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("marks changed source material and clears the warning after save", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchSummary).mockResolvedValue(summary(true));
    vi.mocked(updateSummary).mockResolvedValue(summary(false));

    render(
      <DailySummaryCard
        date="2026-07-23"
        refreshKey={0}
        onChanged={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/Source entries changed/),
    ).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Save summary" }));

    await waitFor(() =>
      expect(updateSummary).toHaveBeenCalledWith(
        "2026-07-23",
        "The original summary.",
      ),
    );
    expect(screen.queryByText(/Source entries changed/)).toBeNull();
  });

  it("rechecks freshness when another part of the day changes", async () => {
    vi.mocked(fetchSummary)
      .mockResolvedValueOnce(summary(false))
      .mockResolvedValueOnce(summary(true));

    const { rerender } = render(
      <DailySummaryCard
        date="2026-07-23"
        refreshKey={0}
        onChanged={vi.fn()}
      />,
    );
    await screen.findByDisplayValue("The original summary.");

    rerender(
      <DailySummaryCard
        date="2026-07-23"
        refreshKey={1}
        onChanged={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/Source entries changed/),
    ).toBeTruthy();
    expect(fetchSummary).toHaveBeenCalledTimes(2);
  });

  it("keeps provider details out of the daily summary UI", async () => {
    vi.mocked(fetchSummary).mockResolvedValue({
      ...summary(false),
      provider: "NVIDIA Build API",
      model: "nvidia/example-model",
      is_user_edited: false,
    });

    render(
      <DailySummaryCard
        date="2026-07-23"
        refreshKey={0}
        onChanged={vi.fn()}
      />,
    );

    expect(
      await screen.findByText("Generated automatically"),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Generate summary" }),
    ).toBeTruthy();
    expect(screen.queryByText(/NVIDIA|nvidia/)).toBeNull();
  });
});

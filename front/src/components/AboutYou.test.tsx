import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchContextPreview, fetchGoals } from "../api";
import { authStub, testUser } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import { todayAsLocalDate } from "../time";
import AboutYou from "./AboutYou";

vi.mock("../api", () => ({
  archiveHabit: vi.fn(),
  createGoal: vi.fn(),
  deleteGoal: vi.fn(),
  fetchContextPreview: vi.fn(),
  fetchGoals: vi.fn(),
  renameHabit: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("AboutYou", () => {
  beforeEach(() => {
    vi.mocked(fetchGoals).mockResolvedValue([
      {
        id: 1,
        kind: "long_term",
        title: "Launch Cadence",
        notes: "",
        sort_order: 0,
        updated_at: null,
      },
    ]);
  });

  it("saves the about text on leave and previews what Cadence sees", async () => {
    const user = userEvent.setup();
    const updateAbout = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue(
      authStub({ aiEnabled: true, user: { ...testUser, about: "" }, updateAbout }),
    );
    vi.mocked(fetchContextPreview).mockResolvedValue({
      text: "About them:\nFounder.\n\nGoals:\n- Long term: Launch Cadence",
    });
    render(<AboutYou habits={[]} onHabitsChanged={vi.fn()} />);

    await user.type(screen.getByRole("textbox", { name: "About you" }), "Founder.");
    await user.tab();
    expect(updateAbout).toHaveBeenCalledWith("Founder.");

    await user.click(screen.getByText("What Cadence sees"));
    expect(fetchContextPreview).toHaveBeenCalledWith(todayAsLocalDate());
    expect(
      (await screen.findByText(/Long term: Launch Cadence/)).textContent,
    ).toContain("About them:\nFounder.");
  });

  it("keeps goals but hides the AI-only parts when AI is off", () => {
    vi.mocked(useAuth).mockReturnValue(authStub());
    render(<AboutYou habits={[]} onHabitsChanged={vi.fn()} />);

    screen.getByText("Goals");
    expect(screen.queryByRole("textbox", { name: "About you" })).toBeNull();
    expect(screen.queryByText("What Cadence sees")).toBeNull();
  });
});

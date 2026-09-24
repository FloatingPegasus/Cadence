import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addLog, fetchLogs, type LogEntry } from "../../api";
import { authStub } from "../../authTest";
import { useAuth } from "../../contexts/AuthContext";
import LogNote from "./LogNote";

vi.mock("../../api", () => ({ addLog: vi.fn(), fetchLogs: vi.fn() }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

function entry(
  id: number,
  content: string,
  hour: number | null,
  role = "user",
): LogEntry {
  return { id, role, content, hour, created_at: "2026-07-24T09:00:00Z" };
}

function renderNote(onStartFocus = vi.fn()) {
  render(
    <LogNote
      date="2026-07-24"
      hour={15}
      refreshKey={0}
      onStartFocus={onStartFocus}
      onChanged={vi.fn()}
    />,
  );
}

describe("LogNote", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
  });

  it("posts a log for the current hour and shows it as the latest", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchLogs).mockResolvedValue([]);
    vi.mocked(addLog).mockResolvedValue(entry(1, "Pitch deck, slide 6", 15));
    renderNote();

    screen.getByRole("heading", { name: "3 PM" });
    await user.type(
      screen.getByRole("textbox", { name: "What are you doing?" }),
      "Pitch deck, slide 6{Enter}",
    );

    expect(addLog).toHaveBeenCalledWith("2026-07-24", "Pitch deck, slide 6", 15);
    await screen.findByText("Pitch deck, slide 6");
    expect(
      (screen.getByRole("textbox", { name: "What are you doing?" }) as HTMLInputElement)
        .value,
    ).toBe("");
  });

  it("shows the latest exchange and opens the day's thread in place", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchLogs).mockResolvedValue([
      entry(1, "Standup", 9),
      entry(2, "Outline", 11),
      entry(3, "Wrote the intro", 14),
      entry(4, "Keep the intro short.", 14, "assistant"),
    ]);
    renderNote();

    await screen.findByText("Wrote the intro");
    screen.getByText("Keep the intro short.");
    screen.getByText("2 PM");
    expect(screen.queryByText("Standup")).toBeNull();
    screen.getByText("3 hours logged");

    await user.click(screen.getByRole("button", { name: "See today" }));
    screen.getByText("Standup");
    screen.getByText("Outline");
    await user.click(screen.getByRole("button", { name: "Show less" }));
    expect(screen.queryByText("Standup")).toBeNull();
  });

  it("starts focus", async () => {
    const user = userEvent.setup();
    const onStartFocus = vi.fn();
    vi.mocked(fetchLogs).mockResolvedValue([]);
    renderNote(onStartFocus);

    await user.click(screen.getByRole("button", { name: "Start focus" }));
    expect(onStartFocus).toHaveBeenCalledOnce();
  });
});

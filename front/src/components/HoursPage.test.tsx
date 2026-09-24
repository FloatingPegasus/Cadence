import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addLog, deleteLog, fetchLogs, updateLog, type LogEntry } from "../api";
import { authStub } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import HoursPage from "./HoursPage";

vi.mock("../api", () => ({
  addLog: vi.fn(),
  deleteLog: vi.fn(),
  fetchLogs: vi.fn(),
  updateLog: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

function log(id: number, hour: number | null, content: string): LogEntry {
  return {
    id,
    role: "user",
    content,
    hour,
    created_at: "2026-07-24T09:15:00Z",
  };
}

function renderPage() {
  render(
    <HoursPage date="2026-07-24" onSelectDate={vi.fn()} onChanged={vi.fn()} />,
  );
}

describe("HoursPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue(authStub());
  });

  it("adds a log to an empty hour when the field is left", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchLogs).mockResolvedValue([]);
    vi.mocked(addLog).mockResolvedValue(log(1, 9, "Deep work"));
    renderPage();

    const field = await screen.findByLabelText("9 AM");
    await user.type(field, "Deep work");
    await user.tab();

    expect(addLog).toHaveBeenCalledWith("2026-07-24", "Deep work", 9);
    expect(await screen.findByDisplayValue("Deep work")).toBeTruthy();
  });

  it("groups logs by hour, edits in place, and deletes when cleared", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchLogs).mockResolvedValue([
      log(1, 14, "Outline"),
      log(2, 14, "Then the draft"),
      { ...log(3, null, "A reply"), role: "assistant" },
    ]);
    vi.mocked(updateLog).mockResolvedValue(log(1, 14, "Outline done"));
    vi.mocked(deleteLog).mockResolvedValue(undefined);
    renderPage();

    await screen.findByDisplayValue("Outline");
    const [first, second] = screen.getAllByLabelText("2 PM");
    expect((first as HTMLInputElement).value).toBe("Outline");
    expect((second as HTMLInputElement).value).toBe("Then the draft");
    expect(screen.queryByDisplayValue("A reply")).toBeNull();

    await user.type(first, " done");
    await user.tab();
    expect(updateLog).toHaveBeenCalledWith("2026-07-24", 1, "Outline done");

    await user.clear(second);
    await user.tab();
    expect(deleteLog).toHaveBeenCalledWith("2026-07-24", 2);
    await waitFor(() => expect(screen.getAllByLabelText("2 PM")).toHaveLength(1));
  });

  it("adds another log to an hour that already has one", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchLogs).mockResolvedValue([log(1, 10, "Standup")]);
    vi.mocked(addLog).mockResolvedValue(log(2, 10, "Reviewed a PR"));
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Add to 10 AM" }));
    await user.keyboard("Reviewed a PR{Enter}");

    expect(addLog).toHaveBeenCalledWith("2026-07-24", "Reviewed a PR", 10);
    expect(await screen.findByDisplayValue("Reviewed a PR")).toBeTruthy();
  });
});

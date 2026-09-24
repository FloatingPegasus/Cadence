import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addLog, fetchLogs, type LogEntry } from "../../api";
import { authStub, testUser } from "../../authTest";
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

function withAi() {
  vi.mocked(useAuth).mockReturnValue(
    authStub({
      aiEnabled: true,
      user: { ...testUser, ai_processing_consent: true },
    }),
  );
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

function field() {
  return screen.getByRole("textbox", { name: "What are you doing?" });
}

describe("LogNote", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
    vi.mocked(fetchLogs).mockResolvedValue([]);
  });

  it("posts a log for the current hour and shows it as the latest", async () => {
    const user = userEvent.setup();
    vi.mocked(addLog).mockResolvedValue({
      log: entry(1, "Pitch deck, slide 6", 15),
      reply: null,
      notice: null,
    });
    renderNote();

    screen.getByRole("heading", { name: "3 PM" });
    await user.type(field(), "Pitch deck, slide 6{Enter}");

    expect(addLog).toHaveBeenCalledWith(
      "2026-07-24",
      "Pitch deck, slide 6",
      15,
      false,
    );
    await screen.findByText("Pitch deck, slide 6");
    expect((field() as HTMLInputElement).value).toBe("");
    expect(screen.queryByRole("button", { name: "Save only" })).toBeNull();
  });

  it("asks for a reply when AI is on and shows it under the log", async () => {
    const user = userEvent.setup();
    withAi();
    let finish: (value: Awaited<ReturnType<typeof addLog>>) => void = () => {};
    vi.mocked(addLog).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderNote();

    await user.type(field(), "Stuck on the deck{Enter}");
    expect(addLog).toHaveBeenCalledWith("2026-07-24", "Stuck on the deck", 15, true);
    screen.getByLabelText("Replying");

    finish({
      log: entry(1, "Stuck on the deck", 15),
      reply: entry(2, "Start with slide one.", 15, "assistant"),
      notice: null,
    });
    await screen.findByText("Start with slide one.");
    expect(screen.queryByLabelText("Replying")).toBeNull();
  });

  it("saves without a reply and shows any notice", async () => {
    const user = userEvent.setup();
    withAi();
    vi.mocked(addLog).mockResolvedValue({
      log: entry(1, "Rough night", 15),
      reply: null,
      notice: "Call 14416.",
    });
    renderNote();

    await user.type(field(), "Rough night");
    await user.click(screen.getByRole("button", { name: "Save only" }));

    expect(addLog).toHaveBeenCalledWith("2026-07-24", "Rough night", 15, false);
    expect((await screen.findByRole("status")).textContent).toBe("Call 14416.");
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
    renderNote(onStartFocus);

    await user.click(screen.getByRole("button", { name: "Start focus" }));
    expect(onStartFocus).toHaveBeenCalledOnce();
  });
});

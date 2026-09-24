import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTask, fetchTasks, updateTask } from "../api";
import { authStub } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import { shiftLocalDate, todayAsLocalDate } from "../time";
import TasksPage from "./TasksPage";

vi.mock("../api", () => ({
  createTask: vi.fn(),
  fetchTasks: vi.fn(),
  updateTask: vi.fn(),
}));
vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

function task(overrides: Partial<{
  id: number;
  title: string;
  due_date: string | null;
  is_completed: boolean;
  is_abandoned: boolean;
  completed_at: string | null;
}> = {}) {
  return {
    id: 9,
    title: "Water the plants",
    due_date: todayAsLocalDate(),
    is_completed: false,
    is_abandoned: false,
    completed_at: null,
    ...overrides,
  };
}

describe("TasksPage", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
  });

  it("adds a dated task and can mark it complete", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTasks).mockResolvedValue([]);
    vi.mocked(createTask).mockResolvedValue(
      task({
        id: 4,
        title: "Send the notes",
      }),
    );
    vi.mocked(updateTask).mockResolvedValue(
      task({
        id: 4,
        title: "Send the notes",
        is_completed: true,
        completed_at: "2026-07-24T12:00:00",
      }),
    );

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);
    screen.getByRole("heading", { name: "Tasks" });
    expect((screen.getByLabelText("Due") as HTMLInputElement).value).toBe(
      todayAsLocalDate(),
    );
    await user.type(screen.getByLabelText("Add a task"), "Send the notes");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(createTask).toHaveBeenCalledWith(
      "Send the notes",
      todayAsLocalDate(),
    );
    await user.click(
      await screen.findByRole("checkbox", {
        name: "Mark Send the notes complete",
      }),
    );
    expect(updateTask).toHaveBeenCalledWith(4, { is_completed: true });
  });

  it("carries a task to the next day", async () => {
    const user = userEvent.setup();
    const current = task();
    const next = shiftLocalDate(todayAsLocalDate(), 1);
    vi.mocked(fetchTasks).mockResolvedValue([current]);
    vi.mocked(updateTask).mockResolvedValue({ ...current, due_date: next });

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Carry forward" }),
    );
    expect(updateTask).toHaveBeenCalledWith(9, { due_date: next });
  });

  it("groups open tasks by when they are due", async () => {
    const user = userEvent.setup();
    const today = todayAsLocalDate();
    const yesterday = shiftLocalDate(today, -1);
    const later = shiftLocalDate(today, 5);
    vi.mocked(fetchTasks).mockResolvedValue([
      task({ id: 1, title: "Reply to the landlord", due_date: yesterday }),
      task({ id: 2, title: "Send the invoice", due_date: today }),
      task({ id: 3, title: "Book the dentist", due_date: later }),
      task({ id: 4, title: "Water the plants", due_date: null }),
    ]);
    vi.mocked(updateTask).mockResolvedValue(
      task({ id: 1, title: "Reply to the landlord", due_date: today }),
    );

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);

    const headings = (await screen.findAllByRole("heading", { level: 2 })).map(
      (heading) => heading.textContent,
    );
    expect(headings).toEqual(["Earlier", "Today", "Upcoming", "No date"]);
    const earlier = screen.getByRole("heading", { name: "Earlier" })
      .parentElement as HTMLElement;
    within(earlier).getByText("Reply to the landlord");
    within(earlier).getByText("Yesterday");

    await user.click(
      screen.getByRole("button", { name: "Due Reply to the landlord" }),
    );
    const input = screen.getByLabelText("Due Reply to the landlord");
    fireEvent.change(input, { target: { value: today } });
    expect(updateTask).toHaveBeenCalledWith(1, { due_date: today });
  });

  it("abandons a task and can restore it", async () => {
    const user = userEvent.setup();
    const current = task();
    vi.mocked(fetchTasks).mockResolvedValue([current]);
    vi.mocked(updateTask)
      .mockResolvedValueOnce({ ...current, is_abandoned: true })
      .mockResolvedValueOnce({ ...current, is_abandoned: false });

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Abandon Water the plants" }),
    );
    expect(updateTask).toHaveBeenCalledWith(9, { is_abandoned: true });
    await user.click(
      await screen.findByRole("button", { name: "Restore Water the plants" }),
    );
    expect(updateTask).toHaveBeenCalledWith(9, { is_abandoned: false });
  });
});

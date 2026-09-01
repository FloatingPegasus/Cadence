import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createTask, deleteTask, fetchTasks, updateTask } from "../api";
import { todayAsLocalDate } from "../time";
import TasksPage from "./TasksPage";

vi.mock("../api", () => ({
  createTask: vi.fn(),
  deleteTask: vi.fn(),
  fetchTasks: vi.fn(),
  updateTask: vi.fn(),
}));

describe("TasksPage", () => {
  it("adds a dated task and can mark it complete", async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTasks).mockResolvedValue([]);
    vi.mocked(createTask).mockResolvedValue({
      id: 4,
      title: "Send the notes",
      due_date: todayAsLocalDate(),
      is_completed: false,
      completed_at: null,
    });
    vi.mocked(updateTask).mockResolvedValue({
      id: 4,
      title: "Send the notes",
      due_date: todayAsLocalDate(),
      is_completed: true,
      completed_at: "2026-07-24T12:00:00",
    });

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

  it("keeps a removed task until the undo window closes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({
      advanceTimers: vi.advanceTimersByTime.bind(vi),
    });
    vi.mocked(fetchTasks).mockResolvedValue([
      {
        id: 9,
        title: "Water the plants",
        due_date: todayAsLocalDate(),
        is_completed: false,
        completed_at: null,
      },
    ]);
    vi.mocked(deleteTask).mockResolvedValue(undefined as never);

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Remove Water the plants" }),
    );

    expect(screen.queryByText("Water the plants")).toBeNull();
    expect(deleteTask).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Undo" }));

    expect(screen.getByText("Water the plants")).toBeTruthy();
    vi.advanceTimersByTime(10000);
    expect(deleteTask).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("deletes a removed task once the undo window closes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({
      advanceTimers: vi.advanceTimersByTime.bind(vi),
    });
    vi.mocked(fetchTasks).mockResolvedValue([
      {
        id: 9,
        title: "Water the plants",
        due_date: todayAsLocalDate(),
        is_completed: false,
        completed_at: null,
      },
    ]);
    vi.mocked(deleteTask).mockResolvedValue(undefined as never);

    render(<TasksPage refreshKey={0} onChanged={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Remove Water the plants" }),
    );

    vi.advanceTimersByTime(6000);
    await waitFor(() => expect(deleteTask).toHaveBeenCalledWith(9));
    vi.useRealTimers();
  });
});

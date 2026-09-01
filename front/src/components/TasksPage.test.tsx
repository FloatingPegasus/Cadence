import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createTask, fetchTasks, updateTask } from "../api";
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
});

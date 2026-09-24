import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api";
import { authStub } from "../../authTest";
import { useAuth } from "../../contexts/AuthContext";
import { shiftLocalDate, todayAsLocalDate } from "../../time";
import TodayList from "./TodayList";

vi.mock("../../api", () => ({
  createHabit: vi.fn(),
  createTask: vi.fn(),
  fetchDayHabits: vi.fn(),
  fetchTasks: vi.fn(),
  toggleHabit: vi.fn(),
  updateTask: vi.fn(),
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

const today = todayAsLocalDate();

function task(
  id: number,
  title: string,
  due_date: string | null,
  is_completed = false,
): api.TaskItem {
  return {
    id,
    title,
    due_date,
    is_completed,
    is_abandoned: false,
    completed_at: null,
  };
}

function renderList(props: Partial<Parameters<typeof TodayList>[0]> = {}) {
  render(
    <TodayList
      date={today}
      refreshKey={0}
      onHabitsChanged={vi.fn()}
      onChanged={vi.fn()}
      {...props}
    />,
  );
}

describe("TodayList", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(authStub());
    vi.mocked(api.fetchDayHabits).mockResolvedValue([
      { id: 1, name: "Read 20 pages", is_archived: false, completed: true },
    ]);
    vi.mocked(api.fetchTasks).mockResolvedValue([
      task(10, "Send the invoice", today),
      task(11, "Reply to the landlord", shiftLocalDate(today, -2)),
      task(12, "Book the dentist", shiftLocalDate(today, 3)),
    ]);
  });

  it("lists habits and today's tasks, and checks one off", async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateTask).mockResolvedValue(task(10, "Send the invoice", today, true));
    renderList();

    const habit = await screen.findByRole("checkbox", { name: /Read 20 pages/ });
    expect(habit.getAttribute("aria-checked")).toBe("true");
    screen.getByRole("img", { name: "Daily" });
    screen.getByText("1 of 2 done");
    expect(screen.queryByText("Book the dentist")).toBeNull();

    await user.click(screen.getByRole("checkbox", { name: "Send the invoice" }));
    expect(api.updateTask).toHaveBeenCalledWith(10, { is_completed: true });
    await screen.findByText("2 of 2 done");
  });

  it("reveals open tasks from earlier in place", async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(await screen.findByRole("button", { name: "1 from earlier" }));
    screen.getByRole("checkbox", { name: "Reply to the landlord" });
    screen.getByText("1 of 3 done");
    await user.click(screen.getByRole("button", { name: "Hide earlier" }));
    expect(screen.queryByText("Reply to the landlord")).toBeNull();
  });

  it("adds a task for the day, or a habit when marked Daily", async () => {
    const user = userEvent.setup();
    const onHabitsChanged = vi.fn();
    vi.mocked(api.createTask).mockResolvedValue(task(13, "Call mom", today));
    vi.mocked(api.createHabit).mockResolvedValue({
      id: 2,
      name: "Stretch",
      is_archived: false,
    });
    renderList({ onHabitsChanged });

    const field = await screen.findByRole("textbox", {
      name: "Add something for today",
    });
    await user.type(field, "Call mom{Enter}");
    expect(api.createTask).toHaveBeenCalledWith("Call mom", today);
    await screen.findByRole("checkbox", { name: "Call mom" });

    await user.type(field, "Stretch");
    await user.click(screen.getByRole("button", { name: "Daily" }));
    await user.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(api.createHabit).toHaveBeenCalledWith("Stretch"));
    await screen.findByRole("checkbox", { name: /Stretch/ });
    expect(onHabitsChanged).toHaveBeenCalledOnce();
  });
});

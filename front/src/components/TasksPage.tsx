import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  createTask,
  fetchTasks,
  updateTask,
  type TaskItem,
} from "../api";
import { shiftLocalDate, todayAsLocalDate } from "../time";
import { useAuth } from "../contexts/AuthContext";

interface TasksPageProps {
  refreshKey: number;
  onChanged: () => void;
}

export default function TasksPage({ refreshKey, onChanged }: TasksPageProps) {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState(todayAsLocalDate);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!user) {
      setTasks([]);
      setIsLoading(false);
      return;
    }
    const initial = !loaded.current;
    if (initial) setIsLoading(true);
    fetchTasks()
      .then((rows) => {
        if (cancelled) return;
        loaded.current = true;
        setTasks(rows);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error ? caught.message : "Could not load tasks",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, user?.id]);

  async function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = title.trim();
    if (!name) return;
    setIsSaving(true);
    setError(null);
    try {
      const created = await createTask(name, dueDate || null);
      setTasks((current) => [...current, created]);
      setTitle("");
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add the task",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function patch(task: TaskItem, next: Partial<TaskItem>) {
    setError(null);
    setTasks((current) =>
      current.map((item) =>
        item.id === task.id ? { ...item, ...next } : item,
      ),
    );
    const fields: {
      due_date?: string | null;
      is_completed?: boolean;
      is_abandoned?: boolean;
    } = {};
    if (next.due_date !== undefined) fields.due_date = next.due_date;
    if (next.is_completed !== undefined) fields.is_completed = next.is_completed;
    if (next.is_abandoned !== undefined) fields.is_abandoned = next.is_abandoned;
    try {
      const saved = await updateTask(task.id, fields);
      setTasks((current) =>
        current.map((item) => (item.id === saved.id ? saved : item)),
      );
      onChanged();
    } catch (caught) {
      setTasks((current) =>
        current.map((item) => (item.id === task.id ? task : item)),
      );
      setError(
        caught instanceof Error ? caught.message : "Could not update the task",
      );
    }
  }

  const today = todayAsLocalDate();
  const open = tasks.filter(
    (task) => !task.is_completed && !task.is_abandoned,
  );
  const done = tasks.filter((task) => task.is_completed && !task.is_abandoned);
  const abandoned = tasks.filter((task) => task.is_abandoned);
  const groups = [
    {
      label: "Earlier",
      items: open.filter((task) => task.due_date && task.due_date < today),
    },
    { label: "Today", items: open.filter((task) => task.due_date === today) },
    {
      label: "Upcoming",
      items: open.filter((task) => task.due_date && task.due_date > today),
    },
    { label: "No date", items: open.filter((task) => !task.due_date) },
  ];

  return (
    <div>
      <h1 className="cadence-title text-2xl font-medium text-neutral-100">
        Tasks
      </h1>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
      <form
        onSubmit={addTask}
        className="cadence-surface mt-6 flex flex-col items-start gap-2"
      >
        <div className="flex w-full gap-2">
          <label htmlFor="new-task" className="sr-only">
            Add a task
          </label>
          <input
            id="new-task"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Add a task"
            maxLength={200}
            className="cadence-field min-w-0 flex-1"
          />
          <button
            type="submit"
            disabled={isSaving || title.trim().length === 0}
            className={`cadence-chip min-h-11 px-3.5 sm:text-xs ${title.trim() ? "cadence-chip-solid" : "cadence-chip-ghost"}`}
          >
            {isSaving ? "Adding" : "Add"}
          </button>
        </div>
        <label htmlFor="new-task-date" className="sr-only">
          Due
        </label>
        <input
          id="new-task-date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
          className="cadence-chip min-h-11 px-2 py-2 text-base text-neutral-300 outline-none sm:min-h-0 sm:py-1.5 sm:text-xs"
        />
      </form>
      {isLoading && tasks.length === 0 ? (
        <p className="mt-6 text-sm text-neutral-600">Loading tasks...</p>
      ) : (
        groups.map((group) =>
          group.items.length > 0 ? (
            <section key={group.label} className="cadence-surface mt-4">
              <h2 className="cadence-kicker">{group.label}</h2>
              <div className="mt-1">
                {group.items.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    today={today}
                    onToggle={() =>
                      void patch(task, { is_completed: !task.is_completed })
                    }
                    onDueChange={(value) =>
                      void patch(task, { due_date: value || null })
                    }
                    onCarryForward={() =>
                      void patch(task, {
                        due_date: shiftLocalDate(task.due_date ?? today, 1),
                      })
                    }
                    onAbandon={() => void patch(task, { is_abandoned: true })}
                  />
                ))}
              </div>
            </section>
          ) : null,
        )
      )}
      {done.length > 0 ? (
        <div className="cadence-surface mt-6">
          <h2 className="cadence-kicker">Done</h2>
          <div className="mt-1">
            {done.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                today={today}
                onToggle={() =>
                  void patch(task, { is_completed: !task.is_completed })
                }
                onDueChange={(value) =>
                  void patch(task, { due_date: value || null })
                }
              />
            ))}
          </div>
        </div>
      ) : null}
      {abandoned.length > 0 ? (
        <div className="cadence-surface mt-6">
          <h2 className="cadence-kicker">Abandoned</h2>
          <div className="mt-1">
            {abandoned.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                today={today}
                onRestore={() => void patch(task, { is_abandoned: false })}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function dueLabel(due: string, today: string) {
  if (due === today) return "Today";
  if (due === shiftLocalDate(today, 1)) return "Tomorrow";
  if (due === shiftLocalDate(today, -1)) return "Yesterday";
  const [year, month, day] = due.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    ...(due.slice(0, 4) !== today.slice(0, 4) ? { year: "numeric" } : {}),
  });
}

function CalendarMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1rem] w-[1rem]"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="4"
        y="5.5"
        width="16"
        height="14"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M4 10h16M8.5 3.5v3.5M15.5 3.5v3.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function DueControl({
  task,
  today,
  onDueChange,
}: {
  task: TaskItem;
  today: string;
  onDueChange: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const label =
    task.due_date && task.due_date !== today
      ? dueLabel(task.due_date, today)
      : null;

  if (editing) {
    return (
      <>
        <label className="sr-only" htmlFor={`task-due-${task.id}`}>
          Due {task.title}
        </label>
        <input
          id={`task-due-${task.id}`}
          type="date"
          autoFocus
          value={task.due_date ?? ""}
          onChange={(event) => {
            onDueChange(event.target.value);
            setEditing(false);
          }}
          onBlur={() => setEditing(false)}
          className="cadence-chip min-h-11 px-2 py-1.5 text-base text-neutral-400 outline-none sm:min-h-0 sm:text-xs"
        />
      </>
    );
  }

  return (
    <button
      type="button"
      aria-label={`Due ${task.title}`}
      onClick={() => setEditing(true)}
      className={
        label
          ? "min-h-11 shrink-0 px-2 text-xs text-neutral-400 hover:text-neutral-200"
          : "inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center text-neutral-500 hover:text-neutral-200"
      }
    >
      {label ?? <CalendarMark />}
    </button>
  );
}

function TaskRow({
  task,
  today,
  onToggle,
  onDueChange,
  onCarryForward,
  onAbandon,
  onRestore,
}: {
  task: TaskItem;
  today: string;
  onToggle?: () => void;
  onDueChange?: (value: string) => void;
  onCarryForward?: () => void;
  onAbandon?: () => void;
  onRestore?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 py-1 sm:flex-nowrap">
      {onToggle ? (
        <input
          type="checkbox"
          checked={task.is_completed}
          onChange={onToggle}
          aria-label={`Mark ${task.title} complete`}
          className="cadence-check"
        />
      ) : null}
      <span
        className={
          task.is_abandoned || task.is_completed
            ? "min-w-0 flex-1 truncate py-2 text-sm text-neutral-500 line-through"
            : "min-w-0 flex-1 truncate py-2 text-sm text-neutral-200"
        }
      >
        {task.title}
      </span>
      <div className="flex w-full min-w-0 items-center justify-end sm:w-auto">
        {onDueChange ? (
          <DueControl task={task} today={today} onDueChange={onDueChange} />
        ) : null}
        {onCarryForward ? (
          <button
            type="button"
            onClick={onCarryForward}
            className="min-h-11 shrink-0 px-2 text-xs text-neutral-500 hover:text-neutral-200"
          >
            Carry forward
          </button>
        ) : null}
        {onAbandon ? (
          <button
            type="button"
            onClick={onAbandon}
            aria-label={`Abandon ${task.title}`}
            className="min-h-11 shrink-0 px-2 text-xs text-neutral-500 hover:text-neutral-200"
          >
            Abandon
          </button>
        ) : null}
        {onRestore ? (
          <button
            type="button"
            onClick={onRestore}
            aria-label={`Restore ${task.title}`}
            className="min-h-11 shrink-0 px-2 text-xs text-neutral-500 hover:text-neutral-200"
          >
            Restore
          </button>
        ) : null}
      </div>
    </div>
  );
}

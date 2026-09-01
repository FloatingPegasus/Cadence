import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  createTask,
  deleteTask,
  fetchTasks,
  updateTask,
  type TaskItem,
} from "../api";
import { todayAsLocalDate } from "../time";

interface TasksPageProps {
  refreshKey: number;
  onChanged: () => void;
}

export default function TasksPage({ refreshKey, onChanged }: TasksPageProps) {
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
  }, [refreshKey]);

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

  async function toggle(task: TaskItem) {
    const next = !task.is_completed;
    setError(null);
    setTasks((current) =>
      current.map((item) =>
        item.id === task.id ? { ...item, is_completed: next } : item,
      ),
    );
    try {
      const saved = await updateTask(task.id, { is_completed: next });
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

  async function changeDue(task: TaskItem, next: string) {
    const due_date = next || null;
    setError(null);
    setTasks((current) =>
      current.map((item) =>
        item.id === task.id ? { ...item, due_date } : item,
      ),
    );
    try {
      const saved = await updateTask(task.id, { due_date });
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

  async function remove(task: TaskItem) {
    setError(null);
    setTasks((current) => current.filter((item) => item.id !== task.id));
    try {
      await deleteTask(task.id);
      onChanged();
    } catch (caught) {
      setTasks((current) => [...current, task]);
      setError(
        caught instanceof Error ? caught.message : "Could not remove the task",
      );
    }
  }

  const open = tasks.filter((task) => !task.is_completed);
  const done = tasks.filter((task) => task.is_completed);

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
      <div className="cadence-surface mt-10">
        {isLoading && tasks.length === 0 ? (
          <p className="text-sm text-neutral-600">Loading tasks...</p>
        ) : (
          <div className="space-y-1">
            {open.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onToggle={() => void toggle(task)}
                onDueChange={(value) => void changeDue(task, value)}
                onRemove={() => void remove(task)}
              />
            ))}
          </div>
        )}
        <form
          onSubmit={addTask}
          className="mt-5 grid gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_auto]"
        >
          <label htmlFor="new-task" className="sr-only">
            Add a task
          </label>
          <input
            id="new-task"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Add a task"
            maxLength={200}
            className="min-h-11 min-w-0 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-base text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600 sm:min-h-0 sm:text-sm"
          />
          <label htmlFor="new-task-date" className="sr-only">
            Due
          </label>
          <input
            id="new-task-date"
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            className="min-h-11 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-base text-neutral-300 outline-none focus:border-neutral-600 sm:min-h-0 sm:text-sm"
          />
          <button
            type="submit"
            disabled={isSaving || title.trim().length === 0}
            className="min-h-11 rounded-lg bg-neutral-800 px-3 py-2 text-sm text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 sm:text-xs"
          >
            {isSaving ? "Adding" : "Add"}
          </button>
        </form>
      </div>
      {done.length > 0 ? (
        <div className="cadence-surface mt-6">
          <h2 className="cadence-kicker">Done</h2>
          <div className="mt-4 space-y-1">
            {done.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onToggle={() => void toggle(task)}
                onDueChange={(value) => void changeDue(task, value)}
                onRemove={() => void remove(task)}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TaskRow({
  task,
  onToggle,
  onDueChange,
  onRemove,
}: {
  task: TaskItem;
  onToggle: () => void;
  onDueChange: (value: string) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-3 py-3">
      <input
        type="checkbox"
        checked={task.is_completed}
        onChange={onToggle}
        aria-label={`Mark ${task.title} complete`}
        className="h-6 w-6 shrink-0 accent-violet-500"
      />
      <span
        className={
          task.is_completed
            ? "min-w-0 flex-1 truncate text-sm text-neutral-500 line-through"
            : "min-w-0 flex-1 truncate text-sm text-neutral-200"
        }
      >
        {task.title}
      </span>
      <label className="sr-only" htmlFor={`task-due-${task.id}`}>
        Due {task.title}
      </label>
      <input
        id={`task-due-${task.id}`}
        type="date"
        value={task.due_date ?? ""}
        onChange={(event) => onDueChange(event.target.value)}
        className="w-[9.5rem] rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-400 outline-none focus:border-neutral-600"
      />
      <button
        type="button"
        onClick={onRemove}
        className="text-xs text-neutral-500 hover:text-neutral-200"
      >
        Remove
      </button>
    </div>
  );
}

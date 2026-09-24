import { useEffect, useState, type FormEvent } from "react";

import {
  createHabit,
  createTask,
  fetchDayHabits,
  fetchTasks,
  toggleHabit,
  updateTask,
  type DailyHabit,
  type TaskItem,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";
import { todayAsLocalDate } from "../../time";

interface TodayListProps {
  date: string;
  refreshKey: number;
  onHabitsChanged: () => void;
  onChanged: () => void;
}

export default function TodayList({
  date,
  refreshKey,
  onHabitsChanged,
  onChanged,
}: TodayListProps) {
  const { user } = useAuth();
  const [habits, setHabits] = useState<DailyHabit[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [title, setTitle] = useState("");
  const [daily, setDaily] = useState(false);
  const [showEarlier, setShowEarlier] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!user) {
      setHabits([]);
      setTasks([]);
      return;
    }
    Promise.all([fetchDayHabits(date), fetchTasks()])
      .then(([dayHabits, allTasks]) => {
        if (cancelled) return;
        setHabits(dayHabits);
        setTasks(allTasks);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error ? caught.message : "Could not load today",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [date, refreshKey, user?.id]);

  const dueToday = tasks.filter(
    (task) => task.due_date === date && !task.is_abandoned,
  );
  const earlier =
    date === todayAsLocalDate()
      ? tasks.filter(
          (task) =>
            task.due_date !== null &&
            task.due_date < date &&
            !task.is_completed &&
            !task.is_abandoned,
        )
      : [];
  const shownTasks = showEarlier ? [...earlier, ...dueToday] : dueToday;
  const total = habits.length + shownTasks.length;
  const done =
    habits.filter((habit) => habit.completed).length +
    shownTasks.filter((task) => task.is_completed).length;

  async function toggleDailyHabit(habit: DailyHabit) {
    const completed = !habit.completed;
    setError(null);
    setHabits((current) =>
      current.map((item) =>
        item.id === habit.id ? { ...item, completed } : item,
      ),
    );
    try {
      await toggleHabit(habit.id, date, completed ? "1" : "0");
      onChanged();
    } catch (caught) {
      setHabits((current) =>
        current.map((item) => (item.id === habit.id ? habit : item)),
      );
      setError(
        caught instanceof Error ? caught.message : "Could not update the habit",
      );
    }
  }

  async function toggleTask(task: TaskItem) {
    const completed = !task.is_completed;
    setError(null);
    setTasks((current) =>
      current.map((item) =>
        item.id === task.id ? { ...item, is_completed: completed } : item,
      ),
    );
    try {
      const saved = await updateTask(task.id, { is_completed: completed });
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

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = title.trim();
    if (!name) return;
    setIsSaving(true);
    setError(null);
    try {
      if (daily) {
        const habit = await createHabit(name);
        setHabits((current) => [...current, { ...habit, completed: false }]);
        onHabitsChanged();
      } else {
        const created = await createTask(name, date);
        setTasks((current) => [...current, created]);
        onChanged();
      }
      setTitle("");
      setDaily(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add it");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section aria-labelledby="today-list-title">
      <div className="flex items-baseline justify-between gap-3 px-0.5">
        <h2
          id="today-list-title"
          className="cadence-mark text-[1.85rem] text-neutral-100"
        >
          Today
        </h2>
        {total > 0 ? (
          <span className="text-xs text-neutral-500">
            {done} of {total} done
          </span>
        ) : null}
      </div>
      <svg
        className="cadence-wave"
        viewBox="0 0 300 8"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M2 5C40 2 70 7 110 4s80-2 120 1 50 1 68-1"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      <ul className="mt-1">
        {habits.map((habit) => (
          <li key={`habit-${habit.id}`}>
            <SketchCheck
              label={habit.name}
              checked={habit.completed}
              daily
              onToggle={() => void toggleDailyHabit(habit)}
            />
          </li>
        ))}
        {shownTasks.map((task) => (
          <li key={`task-${task.id}`}>
            <SketchCheck
              label={task.title}
              checked={task.is_completed}
              onToggle={() => void toggleTask(task)}
            />
          </li>
        ))}
      </ul>

      <form onSubmit={add} className="flex min-h-12 items-center gap-3 px-0.5">
        <svg
          viewBox="0 0 26 26"
          className="h-[1.6rem] w-[1.6rem] shrink-0 text-neutral-500"
          aria-hidden="true"
        >
          <path
            d="M13 7.5v11M7.6 13.2h10.8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        <label htmlFor="today-new" className="sr-only">
          Add something for today
        </label>
        <input
          id="today-new"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Add something"
          maxLength={200}
          className="min-w-0 flex-1 bg-transparent py-2 text-base text-neutral-100 outline-none placeholder:text-neutral-500"
        />
        {title.trim() ? (
          <>
            <button
              type="button"
              aria-pressed={daily}
              onClick={() => setDaily((value) => !value)}
              className={
                daily
                  ? "cadence-chip cadence-chip-accent text-xs"
                  : "cadence-chip cadence-chip-ghost text-xs"
              }
            >
              Daily
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="cadence-chip cadence-chip-solid text-xs"
            >
              {isSaving ? "Adding" : "Add"}
            </button>
          </>
        ) : null}
      </form>

      {earlier.length > 0 ? (
        <button
          type="button"
          aria-expanded={showEarlier}
          onClick={() => setShowEarlier((value) => !value)}
          className="min-h-11 px-0.5 text-sm text-violet-300 hover:text-violet-200"
        >
          {showEarlier ? "Hide earlier" : `${earlier.length} from earlier`}
        </button>
      ) : null}

      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

function SketchCheck({
  label,
  checked,
  daily = false,
  onToggle,
}: {
  label: string;
  checked: boolean;
  daily?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={onToggle}
      className="cadence-sketch-item"
    >
      <svg viewBox="0 0 26 26" className="cadence-sketch-box" aria-hidden="true">
        <path
          d="M13 3.6c5-.2 9.3 3.7 9.4 8.9.1 5.3-3.9 9.8-9.2 9.9-5.2.1-9.5-4.1-9.6-9.2-.1-4.8 3.7-8.9 8.6-9.4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          className="cadence-sketch-tick"
          pathLength={1}
          d="M8.3 13.6l3.3 3.6 6.8-8.2"
          fill="none"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {daily ? (
        <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-neutral-500" role="img" aria-label="Daily">
          <path
            d="M5 12a7 7 0 0 1 12-4.9M19 12a7 7 0 0 1-12 4.9M17 3.5v3.8h-3.8M7 20.5v-3.8h3.8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
    </button>
  );
}

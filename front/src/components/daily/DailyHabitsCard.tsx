import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  createHabit,
  fetchDayHabits,
  toggleHabit,
  type DailyHabit,
  type Habit,
} from "../../api";

interface DailyHabitsCardProps {
  date: string;
  habits: Habit[];
  refreshKey: number;
  onHabitsChanged: () => void;
  onSourceChanged: () => void;
}

export default function DailyHabitsCard({
  date,
  habits,
  refreshKey,
  onHabitsChanged,
  onSourceChanged,
}: DailyHabitsCardProps) {
  const [dailyHabits, setDailyHabits] = useState<DailyHabit[]>([]);
  const [newName, setNewName] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const initial = loadedDate.current === null;
    if (initial) setIsLoading(true);
    fetchDayHabits(date)
      .then((rows) => {
        if (cancelled) return;
        loadedDate.current = date;
        setDailyHabits(rows);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load your habits",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, refreshKey, habits.length]);

  async function addHabit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setIsSaving(true);
    setError(null);
    try {
      await createHabit(name);
      setNewName("");
      onHabitsChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add habit",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function toggle(habit: DailyHabit) {
    const completed = !habit.completed;
    setError(null);
    setDailyHabits((current) =>
      current.map((item) =>
        item.id === habit.id ? { ...item, completed } : item,
      ),
    );
    try {
      await toggleHabit(habit.id, date, completed ? "1" : "0");
      onSourceChanged();
    } catch (caught) {
      setDailyHabits((current) =>
        current.map((item) =>
          item.id === habit.id ? { ...item, completed: habit.completed } : item,
        ),
      );
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not update the habit",
      );
    }
  }

  return (
    <section
      aria-labelledby="daily-habits-title"
    >
      <h2
        id="daily-habits-title"
        className="cadence-kicker"
      >
        Habits
      </h2>

      {isLoading && dailyHabits.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-600">Loading habits...</p>
      ) : dailyHabits.length > 0 ? (
        <div className="mt-6 space-y-1">
          {dailyHabits.map((habit) => (
            <label
              key={habit.id}
              className="flex items-center justify-between gap-3 py-3 text-sm text-neutral-200"
            >
              <span>{habit.name}</span>
              <input
                type="checkbox"
                checked={habit.completed}
                onChange={() => toggle(habit)}
                aria-label={`Mark ${habit.name} complete for ${date}`}
                className="h-6 w-6 accent-done"
              />
            </label>
          ))}
        </div>
      ) : null}

      <form onSubmit={addHabit} className="mt-5 flex gap-2 sm:gap-3">
        <label htmlFor="new-daily-habit" className="sr-only">
          Add a habit
        </label>
        <input
          id="new-daily-habit"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="Add a habit"
          maxLength={100}
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-base text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600 sm:min-h-0 sm:text-sm"
        />
        <button
          type="submit"
          disabled={isSaving || newName.trim().length === 0}
          className="min-h-11 rounded-lg bg-neutral-800 px-3 py-2 text-sm text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 sm:text-xs"
        >
          {isSaving ? "Adding" : "Add"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

import { useEffect, useState, type FormEvent } from "react";

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

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchDayHabits(date)
      .then(setDailyHabits)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load your practices",
        );
      })
      .finally(() => setIsLoading(false));
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
        caught instanceof Error ? caught.message : "Could not add practice",
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
          : "Could not update the practice",
      );
    }
  }

  return (
    <section
      aria-labelledby="daily-practices-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5"
    >
      <div>
        <h2
          id="daily-practices-title"
          className="text-sm font-medium text-neutral-200"
        >
          Daily practices
        </h2>
        <p className="mt-1 text-xs text-neutral-500">
          Track only what you choose. Nothing is added automatically.
        </p>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">Loading practices…</p>
      ) : dailyHabits.length > 0 ? (
        <div className="mt-4 space-y-2">
          {dailyHabits.map((habit) => (
            <label
              key={habit.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2.5 text-sm text-neutral-300"
            >
              <span>{habit.name}</span>
              <input
                type="checkbox"
                checked={habit.completed}
                onChange={() => toggle(habit)}
                aria-label={`Mark ${habit.name} complete for ${date}`}
                className="h-4 w-4 accent-violet-500"
              />
            </label>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-neutral-500">
          Start with one practice you want to keep visible each day.
        </p>
      )}

      <form onSubmit={addHabit} className="mt-4 flex gap-2">
        <label htmlFor="new-daily-practice" className="sr-only">
          Add a practice
        </label>
        <input
          id="new-daily-practice"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="Add a practice"
          maxLength={100}
          className="min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
        />
        <button
          type="submit"
          disabled={isSaving || newName.trim().length === 0}
          className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
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

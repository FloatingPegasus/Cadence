import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  createHabit,
  fetchDayHabits,
  toggleHabit,
  type DailyHabit,
  type Habit,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";

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
  const { user } = useAuth();
  const [dailyHabits, setDailyHabits] = useState<DailyHabit[]>([]);
  const [newName, setNewName] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!user) {
      setDailyHabits([]);
      setIsLoading(false);
      return;
    }
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
  }, [date, refreshKey, habits.length, user?.id]);

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
              className="flex items-center gap-3 py-3 text-sm text-neutral-200"
            >
              <input
                type="checkbox"
                checked={habit.completed}
                onChange={() => toggle(habit)}
                aria-label={`Mark ${habit.name} complete for ${date}`}
                className="cadence-check"
              />
              <span className={habit.completed ? "text-neutral-500" : undefined}>
                {habit.name}
              </span>
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
          className="cadence-field min-w-0 flex-1"
        />
        <button
          type="submit"
          disabled={isSaving || newName.trim().length === 0}
          className={`cadence-chip min-h-11 px-3.5 sm:text-xs ${newName.trim() ? "cadence-chip-solid" : "cadence-chip-ghost"}`}
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

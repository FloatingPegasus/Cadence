import { useState, type FormEvent } from "react";
import {
  archiveHabit,
  renameHabit,
  type Habit,
} from "../api";

interface HabitManagerProps {
  habits: Habit[];
  onChanged: () => void;
}

export default function HabitManager({
  habits,
  onChanged,
}: HabitManagerProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function saveRename(event: FormEvent, habitId: number) {
    event.preventDefault();
    const name = editingName.trim();
    if (!name) return;
    setError(null);
    try {
      await renameHabit(habitId, name);
      setEditingId(null);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not rename habit",
      );
    }
  }

  async function archive(habitId: number) {
    setError(null);
    try {
      await archiveHabit(habitId);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not archive habit",
      );
    }
  }

  if (habits.length === 0) return null;

  return (
    <details>
      <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-200">
        Manage habits
      </summary>
      <div className="pt-5">
        <div className="space-y-2">
          {habits.map((habit) =>
            editingId === habit.id ? (
              <form
                key={habit.id}
                onSubmit={(event) => saveRename(event, habit.id)}
                className="flex gap-2"
              >
                <input
                  aria-label={`Rename ${habit.name}`}
                  value={editingName}
                  onChange={(event) => setEditingName(event.target.value)}
                  maxLength={100}
                  className="min-w-0 flex-1 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 outline-none"
                />
                <button className="text-xs text-neutral-300">Save</button>
                <button
                  type="button"
                  onClick={() => setEditingId(null)}
                  className="text-xs text-neutral-600"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <div
                key={habit.id}
                className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5"
              >
                <span className="text-sm text-neutral-300">{habit.name}</span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(habit.id);
                      setEditingName(habit.name);
                    }}
                    className="text-xs text-neutral-500 hover:text-neutral-300"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => archive(habit.id)}
                    className="text-xs text-neutral-600 hover:text-red-400"
                  >
                    Archive
                  </button>
                </div>
              </div>
            ),
          )}
        </div>
        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
      </div>
    </details>
  );
}

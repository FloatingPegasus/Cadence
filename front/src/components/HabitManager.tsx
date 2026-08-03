import { useState, type FormEvent } from "react";
import {
  archiveHabit,
  createHabit,
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
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function addHabit(event: FormEvent) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      await createHabit(name);
      setNewName("");
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add habit");
    }
  }

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

  return (
    <details className="mb-6 rounded-lg border border-neutral-800 bg-neutral-950/50">
      <summary className="cursor-pointer px-4 py-3 text-sm text-neutral-400 hover:text-neutral-200">
        Manage daily practices
      </summary>
      <div className="border-t border-neutral-800 p-4">
        <form onSubmit={addHabit} className="flex gap-2">
          <label className="sr-only" htmlFor="new-practice-name">
            New practice name
          </label>
          <input
            id="new-practice-name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Add a practice"
            maxLength={100}
            className="min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
          />
          <button className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 hover:bg-neutral-700">
            Add
          </button>
        </form>
        <div className="mt-4 space-y-2">
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
      <p className="mt-4 text-xs text-neutral-600">
          Archiving removes a practice from new tracking while preserving its
          history.
        </p>
      </div>
    </details>
  );
}

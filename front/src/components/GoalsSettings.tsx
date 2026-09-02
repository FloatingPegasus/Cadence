import { useEffect, useState, type FormEvent } from "react";

import {
  createGoal,
  deleteGoal,
  fetchGoals,
  type GoalKind,
  type UserGoal,
} from "../api";
import { GOAL_KIND_LABELS } from "../time";

const kinds: GoalKind[] = [
  "ultimate",
  "secondary",
  "long_term",
  "short_term",
];

export default function GoalsSettings() {
  const [goals, setGoals] = useState<UserGoal[]>([]);
  const [kind, setKind] = useState<GoalKind>("ultimate");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchGoals()
      .then(setGoals)
      .catch((caught) => {
        setError(
          caught instanceof Error ? caught.message : "Could not load goals",
        );
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function addGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) return;
    setError(null);
    try {
      const created = await createGoal(kind, nextTitle);
      setGoals((current) => [...current, created]);
      setTitle("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add the goal",
      );
    }
  }

  async function removeGoal(goalId: number) {
    setError(null);
    try {
      await deleteGoal(goalId);
      setGoals((current) => current.filter((goal) => goal.id !== goalId));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not remove the goal",
      );
    }
  }

  return (
    <details>
      <summary className="text-sm text-neutral-400 hover:text-neutral-200">
        Goals
      </summary>
      <div className="pt-5">
      <form
        onSubmit={addGoal}
        className="grid gap-2 sm:grid-cols-[8rem_minmax(0,1fr)_auto]"
      >
        <label className="sr-only" htmlFor="goal-kind">
          Goal type
        </label>
        <select
          id="goal-kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as GoalKind)}
          className="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-300 outline-none focus:border-neutral-600"
        >
          {kinds.map((value) => (
            <option key={value} value={value}>
              {GOAL_KIND_LABELS[value]}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="goal-title">
          Goal
        </label>
        <input
          id="goal-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Add a goal"
          maxLength={200}
          className="min-w-0 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
        />
        <button className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700">
          Add
        </button>
      </form>
      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">Loading goals…</p>
      ) : (
        <div className="mt-5 space-y-5">
          {kinds.map((value) => {
            const items = goals.filter((goal) => goal.kind === value);
            if (items.length === 0) return null;
            return (
              <div key={value}>
                <h3 className="text-xs font-medium text-neutral-500">
                  {GOAL_KIND_LABELS[value]}
                </h3>
                <ul className="mt-2 space-y-2">
                  {items.map((goal) => (
                    <li
                      key={goal.id}
                      className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5"
                    >
                      <span className="text-sm text-neutral-300">
                        {goal.title}
                      </span>
                      <button
                        type="button"
                        onClick={() => void removeGoal(goal.id)}
                        className="text-xs text-neutral-600 transition-colors duration-150 hover:text-red-400"
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
      </div>
    </details>
  );
}

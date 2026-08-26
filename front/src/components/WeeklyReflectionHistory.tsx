import { useEffect, useState } from "react";

import {
  fetchWeeklyReflectionHistory,
  type WeeklyReflectionHistoryItem,
} from "../api";

interface WeeklyReflectionHistoryProps {
  currentWeekStart: string;
  refreshKey: number;
  onSelectWeek: (weekStart: string) => void;
}

function shortDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function WeeklyReflectionHistory({
  currentWeekStart,
  refreshKey,
  onSelectWeek,
}: WeeklyReflectionHistoryProps) {
  const [items, setItems] = useState<WeeklyReflectionHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    fetchWeeklyReflectionHistory(8)
      .then(setItems)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load weekly reviews",
        );
      });
  }, [refreshKey]);

  if (items.length === 0 && !error) return null;

  return (
    <section
      aria-labelledby="reflection-history-title"
      className="mt-6 border-t border-neutral-800 pt-5"
    >
      <h3
        id="reflection-history-title"
        className="text-xs font-medium text-neutral-300"
      >
        Earlier reviews
      </h3>

      {error ? (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-label={`Open week ${shortDate(item.week_start)} to ${shortDate(item.week_end)}`}
              aria-current={
                item.week_start === currentWeekStart ? "true" : undefined
              }
              onClick={() => onSelectWeek(item.week_start)}
              className={
                item.week_start === currentWeekStart
                  ? "rounded-lg border border-violet-500/50 bg-violet-500/5 px-3 py-2 text-left"
                  : "rounded-lg border border-neutral-800 px-3 py-2 text-left transition-colors duration-150 hover:bg-neutral-900/60"
              }
            >
              <span className="text-xs text-neutral-300">
                {shortDate(item.week_start)} to {shortDate(item.week_end)}
              </span>
              <span className="mt-1 line-clamp-2 block text-xs leading-5 text-neutral-500">
                {item.excerpt || "Review saved without text"}
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

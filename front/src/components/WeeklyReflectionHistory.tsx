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
      className="mt-16"
    >
      <h3
        id="reflection-history-title"
        className="text-sm text-neutral-400"
      >
        Earlier
      </h3>

      {error ? (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      ) : (
        <div className="mt-6 space-y-5">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-label={`Open week ${shortDate(item.week_start)} to ${shortDate(item.week_end)}`}
              aria-current={
                item.week_start === currentWeekStart ? "true" : undefined
              }
              onClick={() => onSelectWeek(item.week_start)}
              className="block w-full text-left"
            >
              <span
                className={
                  item.week_start === currentWeekStart
                    ? "text-sm text-violet-300"
                    : "text-sm text-neutral-400"
                }
              >
                {shortDate(item.week_start)} to {shortDate(item.week_end)}
              </span>
              {item.excerpt ? (
                <span className="mt-1 line-clamp-2 block text-sm leading-6 text-neutral-500">
                  {item.excerpt}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

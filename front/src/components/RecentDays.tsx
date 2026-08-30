import { useEffect, useState } from "react";
import { fetchRecentDays, type RecentDay } from "../api";

interface RecentDaysProps {
  selectedDate: string | null;
  onSelect: (date: string) => void;
  refreshKey: number;
}

export default function RecentDays({
  selectedDate,
  onSelect,
  refreshKey,
}: RecentDaysProps) {
  const [days, setDays] = useState<RecentDay[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    fetchRecentDays(7)
      .then(setDays)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load recent days",
        );
      });
  }, [refreshKey]);

  if (days.length === 0 && !error) return null;

  return (
    <section className="cadence-surface mt-6">
      <h2 className="cadence-kicker mb-5">Recent days</h2>
      {error && (
        <p role="alert" className="text-xs text-red-400">
          {error}
        </p>
      )}
      <div className="space-y-5">
        {days.map((day) => (
          <button
            key={day.id}
            onClick={() => onSelect(day.date)}
            className="block min-h-11 w-full rounded-lg px-1 py-3 text-left hover:bg-neutral-950/40"
          >
            <span
              className={
                selectedDate === day.date
                  ? "text-sm text-violet-300"
                  : "text-sm text-neutral-400"
              }
            >
              {new Date(`${day.date}T00:00:00`).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </span>
            {day.note_preview ? (
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-neutral-500">
                {day.note_preview}
              </p>
            ) : null}
          </button>
        ))}
      </div>
    </section>
  );
}

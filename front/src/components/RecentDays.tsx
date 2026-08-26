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
    <section className="mt-8">
      <h2 className="mb-3 text-sm font-medium text-neutral-200">Recent days</h2>
      {error && (
        <p role="alert" className="text-xs text-red-400">
          {error}
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {days.map((day) => (
          <button
            key={day.id}
            onClick={() => onSelect(day.date)}
            className={
              selectedDate === day.date
                ? "rounded-lg border border-violet-500/60 bg-violet-500/10 p-3 text-left"
                : "rounded-lg border border-neutral-800 bg-neutral-950/50 p-3 text-left hover:border-neutral-700 hover:bg-neutral-900/70"
            }
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-neutral-300">
                {new Date(`${day.date}T00:00:00`).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })}
              </span>
              {(day.energy_level || day.focus_quality) && (
                <span className="text-[11px] text-neutral-600">
                  E {day.energy_level ?? "-"} · F {day.focus_quality ?? "-"}
                </span>
              )}
            </div>
            <p className="mt-2 line-clamp-2 min-h-8 text-xs leading-4 text-neutral-500">
              {day.note_preview || "No written note."}
            </p>
          </button>
        ))}
      </div>
    </section>
  );
}

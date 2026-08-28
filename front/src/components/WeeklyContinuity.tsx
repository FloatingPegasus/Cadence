import { useEffect, useState } from "react";

import {
  fetchWeeklyContinuity,
  type WeeklyContinuity as WeeklyContinuityData,
} from "../api";
import WeeklyReflectionCard from "./WeeklyReflectionCard";
import WeeklyReflectionHistory from "./WeeklyReflectionHistory";

interface WeeklyContinuityProps {
  anchorDate: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
  refreshKey: number;
  embedded?: boolean;
}

function formatDate(date: string, options: Intl.DateTimeFormatOptions) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", options);
}

function shiftDate(date: string, days: number) {
  const shifted = new Date(`${date}T00:00:00Z`);
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
}

export default function WeeklyContinuity({
  anchorDate,
  selectedDate,
  onSelectDate,
  refreshKey,
}: WeeklyContinuityProps) {
  const [weekAnchor, setWeekAnchor] = useState(anchorDate);
  const [week, setWeek] = useState<WeeklyContinuityData | null>(null);
  const [reflectionVersion, setReflectionVersion] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setWeekAnchor(anchorDate);
  }, [anchorDate]);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setWeek(null);
    fetchWeeklyContinuity(weekAnchor)
      .then(setWeek)
      .catch((caught) => {
        setWeek(null);
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load the week",
        );
      })
      .finally(() => setIsLoading(false));
  }, [weekAnchor, refreshKey]);

  if (!week) {
    return (
      <div>
        <p
          role={error ? "alert" : undefined}
          className={error ? "text-xs text-red-400" : "text-sm text-neutral-500"}
        >
          {error || (isLoading ? "Loading week..." : "No weekly history found.")}
        </p>
      </div>
    );
  }

  const activeDays = week.days.filter((day) => day.has_entry);

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <h2 className="cadence-title text-xl font-medium text-neutral-100">
            {formatDate(week.week_start, {
              month: "short",
              day: "numeric",
            })}
            {" to "}
            {formatDate(week.week_end, {
              month: "short",
              day: "numeric",
            })}
          </h2>
          <div className="flex gap-3">
            <button
              type="button"
              aria-label="Previous week"
              onClick={() => setWeekAnchor(shiftDate(week.week_start, -7))}
              className="text-sm text-neutral-500 transition-colors hover:text-neutral-200"
            >
              ←
            </button>
            <button
              type="button"
              aria-label="Next week"
              onClick={() => setWeekAnchor(shiftDate(week.week_start, 7))}
              className="text-sm text-neutral-500 transition-colors hover:text-neutral-200"
            >
              →
            </button>
          </div>
        </div>
        <p className="text-sm text-neutral-500">
          {week.totals.active_days}{" "}
          {week.totals.active_days === 1 ? "day" : "days"}
          {week.totals.habit_completions > 0
            ? ` · ${week.totals.habit_completions} done`
            : ""}
        </p>
      </div>

      <div className="mt-10">
        {activeDays.length === 0 ? (
          <p className="text-sm text-neutral-500">A quiet week.</p>
        ) : (
          activeDays.map((day) => {
            const preview =
              day.summary_preview ||
              day.note_preview ||
              (day.contexts.length > 0
                ? day.contexts.map((context) => context.name).join(", ")
                : "");
            return (
              <button
                key={day.date}
                type="button"
                onClick={() => onSelectDate(day.date)}
                className={
                  selectedDate === day.date
                    ? "grid w-full grid-cols-[4.5rem_minmax(0,1fr)_auto] gap-4 py-4 text-left"
                    : "grid w-full grid-cols-[4.5rem_minmax(0,1fr)_auto] gap-4 py-4 text-left transition-colors duration-150 hover:text-neutral-200"
                }
              >
                <span
                  className={
                    selectedDate === day.date
                      ? "text-sm text-violet-300"
                      : "text-sm text-neutral-400"
                  }
                >
                  {formatDate(day.date, {
                    weekday: "short",
                    day: "numeric",
                  })}
                </span>
                <span className="min-w-0 truncate text-sm text-neutral-500">
                  {preview}
                </span>
                {day.habit_completions > 0 ? (
                  <span className="text-sm tabular-nums text-neutral-500">
                    {day.habit_completions}
                  </span>
                ) : (
                  <span />
                )}
              </button>
            );
          })
        )}
      </div>

      {week.open_threads.length > 0 && (
        <div className="mt-14">
          <h3 className="text-sm text-neutral-400">Follow-ups</h3>
          <ul className="mt-5 space-y-4">
            {week.open_threads.map((thread) => (
              <li key={thread.id} className="text-sm leading-6 text-neutral-500">
                {thread.content}
              </li>
            ))}
          </ul>
        </div>
      )}
      <WeeklyReflectionCard
        anchorDate={weekAnchor}
        refreshKey={refreshKey}
        onChanged={() =>
          setReflectionVersion((version) => version + 1)
        }
      />
      <WeeklyReflectionHistory
        currentWeekStart={week.week_start}
        refreshKey={refreshKey + reflectionVersion}
        onSelectWeek={setWeekAnchor}
      />
    </section>
  );
}

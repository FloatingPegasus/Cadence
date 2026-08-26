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
  embedded = false,
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
      <div className={embedded ? "pt-4" : "mt-8 border-t border-neutral-800 pt-6"}>
        <p
          role={error ? "alert" : undefined}
          className={error ? "text-xs text-red-400" : "text-sm text-neutral-600"}
        >
          {error || (isLoading ? "Loading week..." : "No weekly history found.")}
        </p>
      </div>
    );
  }

  const activeDays = week.days.filter((day) => day.has_entry);

  return (
    <section
      className={
        embedded ? "pt-4" : "mt-8 border-t border-neutral-800 pt-6"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium text-neutral-200">
              Week in review
            </h2>
            <div className="flex gap-1">
              <button
                type="button"
                aria-label="Previous week"
                onClick={() => setWeekAnchor(shiftDate(week.week_start, -7))}
                className="rounded border border-neutral-800 px-2 py-0.5 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              >
                ←
              </button>
              <button
                type="button"
                aria-label="Next week"
                onClick={() => setWeekAnchor(shiftDate(week.week_start, 7))}
                className="rounded border border-neutral-800 px-2 py-0.5 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              >
                →
              </button>
            </div>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {formatDate(week.week_start, {
              month: "short",
              day: "numeric",
            })}
            {" to "}
            {formatDate(week.week_end, {
              month: "short",
              day: "numeric",
            })}
          </p>
        </div>
        <dl className="flex gap-6 text-xs">
          <div>
            <dt className="text-neutral-600">Active days</dt>
            <dd className="mt-1 font-medium text-neutral-300">
              {week.totals.active_days}
            </dd>
          </div>
          <div>
            <dt className="text-neutral-600">Completions</dt>
            <dd className="mt-1 font-medium text-neutral-300">
              {week.totals.habit_completions}
            </dd>
          </div>
          <div>
            <dt className="text-neutral-600">Closed</dt>
            <dd className="mt-1 font-medium text-neutral-300">
              {week.totals.closed_days}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="border-y border-neutral-800">
          {activeDays.length === 0 ? (
            <p className="py-4 text-sm text-neutral-500">
              No activity recorded for this week.
            </p>
          ) : (
            activeDays.map((day) => (
              <button
                key={day.date}
                type="button"
                onClick={() => onSelectDate(day.date)}
                className={
                  selectedDate === day.date
                    ? "grid w-full grid-cols-[4.5rem_1fr_auto] gap-3 border-b border-violet-500/40 bg-violet-500/5 px-2 py-3 text-left last:border-b-0"
                    : "grid w-full grid-cols-[4.5rem_1fr_auto] gap-3 border-b border-neutral-800 px-2 py-3 text-left transition-colors duration-150 last:border-b-0 hover:bg-neutral-900/60"
                }
              >
                <span className="text-xs font-medium text-neutral-300">
                  {formatDate(day.date, {
                    weekday: "short",
                    day: "numeric",
                  })}
                </span>
                <span className="min-w-0 truncate text-xs text-neutral-500">
                  {day.contexts.length > 0 &&
                    `${day.contexts
                      .map((context) => context.name)
                      .join(", ")} · `}
                  {day.summary_preview ||
                    day.note_preview ||
                    "Activity recorded for this day."}
                </span>
                <span className="text-xs tabular-nums text-neutral-600">
                  {day.habit_completions} done
                </span>
              </button>
            ))
          )}
        </div>

        <div>
          <h3 className="text-xs font-medium text-neutral-400">
            Open follow-ups
          </h3>
          {week.open_threads.length === 0 ? (
            <p className="mt-3 text-xs leading-5 text-neutral-600">
              Nothing is waiting for your attention.
            </p>
          ) : (
            <ul className="mt-3 space-y-3">
              {week.open_threads.map((thread) => (
                <li key={thread.id}>
                  <p className="text-xs leading-5 text-neutral-400">
                    {thread.content}
                  </p>
                  <p className="mt-1 text-[11px] text-neutral-600">
                    From{" "}
                    {formatDate(thread.origin_date, {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
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

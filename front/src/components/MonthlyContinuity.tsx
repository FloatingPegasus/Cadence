import { useEffect, useState } from "react";

import {
  fetchMonthlyContinuity,
  type MonthlyContinuity as MonthlyContinuityData,
} from "../api";
import ContextMonthlyDetail from "./ContextMonthlyDetail";

interface MonthlyContinuityProps {
  anchorDate: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
  refreshKey: number;
  embedded?: boolean;
}

function formatDate(date: string, options: Intl.DateTimeFormatOptions) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", options);
}

function shiftMonth(month: string, offset: number) {
  const [year, monthNumber] = month.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, monthNumber - 1 + offset, 1));
  return `${shifted.getUTCFullYear()}-${String(
    shifted.getUTCMonth() + 1,
  ).padStart(2, "0")}`;
}

export default function MonthlyContinuity({
  anchorDate,
  selectedDate,
  onSelectDate,
  refreshKey,
  embedded = false,
}: MonthlyContinuityProps) {
  const [month, setMonth] = useState(anchorDate.slice(0, 7));
  const [selectedContextId, setSelectedContextId] = useState<number | null>(
    null,
  );
  const [data, setData] = useState<MonthlyContinuityData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMonth(anchorDate.slice(0, 7));
  }, [anchorDate]);

  useEffect(() => {
    setSelectedContextId(null);
  }, [month]);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setData(null);
    fetchMonthlyContinuity(month)
      .then(setData)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load the month",
        );
      })
      .finally(() => setIsLoading(false));
  }, [month, refreshKey]);

  if (isLoading && !data) {
    return (
      <div className={embedded ? "pt-4" : "mt-8 border-t border-neutral-800 pt-6"}>
        <p className="text-sm text-neutral-600">Loading month…</p>
      </div>
    );
  }

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
              Month in review
            </h2>
            <div className="flex gap-1">
              <button
                type="button"
                aria-label="Previous month"
                onClick={() => setMonth((current) => shiftMonth(current, -1))}
                className="rounded border border-neutral-800 px-2 py-0.5 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              >
                ←
              </button>
              <button
                type="button"
                aria-label="Next month"
                onClick={() => setMonth((current) => shiftMonth(current, 1))}
                className="rounded border border-neutral-800 px-2 py-0.5 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              >
                →
              </button>
            </div>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {data
              ? formatDate(data.month_start, {
                  month: "long",
                  year: "numeric",
                })
              : month}
          </p>
        </div>
        {data && (
          <dl className="flex gap-6 text-xs">
            <div>
              <dt className="text-neutral-600">Active days</dt>
              <dd className="mt-1 font-medium text-neutral-300">
                {data.totals.active_days}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-600">Reflections</dt>
              <dd className="mt-1 font-medium text-neutral-300">
                {data.totals.weekly_reflections}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-600">Completions</dt>
              <dd className="mt-1 font-medium text-neutral-300">
                {data.totals.habit_completions}
              </dd>
            </div>
          </dl>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_16rem]">
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Daily traces
              </h3>
              <div className="mt-3 border-y border-neutral-800">
                {data.days.length === 0 ? (
                  <p className="py-4 text-sm text-neutral-500">
                    No meaningful traces recorded this month.
                  </p>
                ) : (
                  data.days.map((day) => (
                    <button
                      key={day.date}
                      type="button"
                      aria-label={`Open daily trace for ${formatDate(day.date, {
                        month: "short",
                        day: "numeric",
                      })}`}
                      onClick={() => onSelectDate(day.date)}
                      className={
                        selectedDate === day.date
                          ? "grid w-full grid-cols-[4.5rem_1fr_auto] gap-3 border-b border-violet-500/40 bg-violet-500/5 px-2 py-3 text-left last:border-b-0"
                          : "grid w-full grid-cols-[4.5rem_1fr_auto] gap-3 border-b border-neutral-800 px-2 py-3 text-left transition-colors duration-150 last:border-b-0 hover:bg-neutral-900/60"
                      }
                    >
                      <span className="text-xs font-medium text-neutral-300">
                        {formatDate(day.date, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                      <span className="min-w-0 truncate text-xs text-neutral-500">
                        {day.contexts.length > 0 &&
                          `${day.contexts
                            .map((context) => context.name)
                            .join(", ")} · `}
                        {day.trace_preview ||
                          (day.status === "closed"
                            ? "Day closed without a written trace."
                            : "Structured activity recorded.")}
                      </span>
                      <span className="text-xs tabular-nums text-neutral-600">
                        {day.habit_completions} done
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Context movement
              </h3>
              {data.contexts.length === 0 ? (
                <p className="mt-3 text-xs leading-5 text-neutral-600">
                  No linked context activity.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.contexts.map((context) => (
                    <li key={context.id}>
                      <button
                        type="button"
                        aria-label={`Open ${context.name} monthly movement`}
                        aria-controls="context-month-detail"
                        aria-expanded={selectedContextId === context.id}
                        onClick={() =>
                          setSelectedContextId((current) =>
                            current === context.id ? null : context.id,
                          )
                        }
                        className="w-full text-left"
                      >
                        <span className="flex justify-between gap-3">
                          <span className="text-xs text-neutral-300">
                            {context.name}
                          </span>
                          <span className="text-[11px] text-neutral-600">
                            {context.active_days} days
                          </span>
                        </span>
                        <span className="mt-1 line-clamp-2 block text-xs leading-5 text-neutral-500">
                          {context.last_trace_preview ||
                            `Last linked ${formatDate(context.last_date, {
                              month: "short",
                              day: "numeric",
                            })}`}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {selectedContextId !== null && (
            <ContextMonthlyDetail
              contextId={selectedContextId}
              month={data.month}
              refreshKey={refreshKey}
              onSelectDate={onSelectDate}
              onClose={() => setSelectedContextId(null)}
            />
          )}

          <div className="mt-6 grid gap-6 border-t border-neutral-800 pt-5 md:grid-cols-2">
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Weekly reflections
              </h3>
              {data.weekly_reflections.length === 0 ? (
                <p className="mt-3 text-xs text-neutral-600">
                  No weekly reflections overlap this month.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.weekly_reflections.map((reflection) => (
                    <li key={reflection.id}>
                      <p className="text-[11px] text-neutral-600">
                        {formatDate(reflection.week_start, {
                          month: "short",
                          day: "numeric",
                        })}
                        {" – "}
                        {formatDate(reflection.week_end, {
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                      <p className="mt-1 line-clamp-3 text-xs leading-5 text-neutral-400">
                        {reflection.excerpt || "Reflection saved without text"}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Open threads
              </h3>
              {data.open_threads.length === 0 ? (
                <p className="mt-3 text-xs text-neutral-600">
                  Nothing unresolved at month end.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {data.open_threads.slice(0, 5).map((thread) => (
                    <li
                      key={thread.id}
                      className="text-xs leading-5 text-neutral-500"
                    >
                      {thread.content}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

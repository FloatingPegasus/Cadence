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
      <div>
        <p className="text-sm text-neutral-500">Loading month...</p>
      </div>
    );
  }

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <h2 className="cadence-title text-xl font-medium text-neutral-100">
            {data
              ? formatDate(data.month_start, {
                  month: "long",
                  year: "numeric",
                })
              : month}
          </h2>
          <div className="flex gap-3">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setMonth((current) => shiftMonth(current, -1))}
              className="text-sm text-neutral-500 transition-colors hover:text-neutral-200"
            >
              ←
            </button>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => setMonth((current) => shiftMonth(current, 1))}
              className="text-sm text-neutral-500 transition-colors hover:text-neutral-200"
            >
              →
            </button>
          </div>
        </div>
        {data && data.totals.active_days > 0 && (
          <p className="text-sm text-neutral-500">
            {data.totals.active_days}{" "}
            {data.totals.active_days === 1 ? "day" : "days"}
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="mt-10">
            {data.days.length === 0 ? (
              <p className="text-sm text-neutral-500">A quiet month.</p>
            ) : (
              data.days.map((day) => {
                const preview =
                  day.trace_preview ||
                  (day.contexts.length > 0
                    ? day.contexts.map((context) => context.name).join(", ")
                    : "");
                return (
                  <button
                    key={day.date}
                    type="button"
                    aria-label={`Open day for ${formatDate(day.date, {
                      month: "short",
                      day: "numeric",
                    })}`}
                    onClick={() => onSelectDate(day.date)}
                    className="grid w-full grid-cols-[4.5rem_minmax(0,1fr)_auto] gap-4 py-4 text-left"
                  >
                    <span
                      className={
                        selectedDate === day.date
                          ? "text-sm text-violet-300"
                          : "text-sm text-neutral-400"
                      }
                    >
                      {formatDate(day.date, {
                        month: "short",
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

          {data.contexts.length > 0 && (
            <div className="mt-14">
              <h3 className="text-sm text-neutral-400">Areas</h3>
              <ul className="mt-5 space-y-5">
                {data.contexts.map((context) => (
                  <li key={context.id}>
                    <button
                      type="button"
                      aria-label={`Open ${context.name} monthly activity`}
                      aria-controls="context-month-detail"
                      aria-expanded={selectedContextId === context.id}
                      onClick={() =>
                        setSelectedContextId((current) =>
                          current === context.id ? null : context.id,
                        )
                      }
                      className="w-full text-left"
                    >
                      <span className="text-sm text-neutral-300">
                        {context.name}
                      </span>
                      {context.last_trace_preview ? (
                        <span className="mt-1 line-clamp-2 block text-sm leading-6 text-neutral-500">
                          {context.last_trace_preview}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {selectedContextId !== null && (
            <ContextMonthlyDetail
              contextId={selectedContextId}
              month={data.month}
              refreshKey={refreshKey}
              onSelectDate={onSelectDate}
              onClose={() => setSelectedContextId(null)}
            />
          )}

          {data.weekly_reflections.length > 0 && (
            <div className="mt-14">
              <h3 className="text-sm text-neutral-400">Reviews</h3>
              <ul className="mt-5 space-y-5">
                {data.weekly_reflections.map((reflection) => (
                  <li key={reflection.id}>
                    <p className="text-sm text-neutral-400">
                      {formatDate(reflection.week_start, {
                        month: "short",
                        day: "numeric",
                      })}
                      {" to "}
                      {formatDate(reflection.week_end, {
                        month: "short",
                        day: "numeric",
                      })}
                    </p>
                    {reflection.excerpt ? (
                      <p className="mt-1 line-clamp-3 text-sm leading-6 text-neutral-500">
                        {reflection.excerpt}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.open_threads.length > 0 && (
            <div className="mt-14">
              <h3 className="text-sm text-neutral-400">Follow-ups</h3>
              <ul className="mt-5 space-y-4">
                {data.open_threads.slice(0, 5).map((thread) => (
                  <li
                    key={thread.id}
                    className="text-sm leading-6 text-neutral-500"
                  >
                    {thread.content}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}

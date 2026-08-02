import { useEffect, useState } from "react";

import {
  fetchContextMonthlyContinuity,
  type ContextMonthlyContinuity,
} from "../api";

interface ContextMonthlyDetailProps {
  contextId: number;
  month: string;
  refreshKey: number;
  onSelectDate: (date: string) => void;
  onClose: () => void;
}

function shortDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function ContextMonthlyDetail({
  contextId,
  month,
  refreshKey,
  onSelectDate,
  onClose,
}: ContextMonthlyDetailProps) {
  const [data, setData] = useState<ContextMonthlyContinuity | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setData(null);
    setError(null);
    fetchContextMonthlyContinuity(contextId, month)
      .then(setData)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load context movement",
        );
      })
      .finally(() => setIsLoading(false));
  }, [contextId, month, refreshKey]);

  return (
    <section
      id="context-month-detail"
      aria-labelledby="context-month-title"
      className="mt-6 border-t border-neutral-800 pt-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3
            id="context-month-title"
            className="text-xs font-medium text-neutral-300"
          >
            {data?.context.name ?? "Context movement"}
          </h3>
          <p className="mt-1 text-xs text-neutral-500">
            Movement inside this context during the selected month.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-neutral-800 px-2.5 py-1 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
        >
          Close
        </button>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">
          Loading context movement…
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      ) : data ? (
        <>
          <dl className="mt-4 flex flex-wrap gap-6 text-xs">
            <div>
              <dt className="text-neutral-600">Active days</dt>
              <dd className="mt-1 text-neutral-300">
                {data.totals.active_days}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-600">Quick entries</dt>
              <dd className="mt-1 text-neutral-300">
                {data.totals.conversation_entries}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-600">Completions</dt>
              <dd className="mt-1 text-neutral-300">
                {data.totals.habit_completions}
              </dd>
            </div>
          </dl>

          {data.previous_activity && (
            <button
              type="button"
              aria-label={`Open prior ${data.context.name} activity from ${shortDate(data.previous_activity.date)}`}
              onClick={() => onSelectDate(data.previous_activity!.date)}
              className="mt-4 w-full rounded-lg border border-neutral-800 px-3 py-2 text-left transition-colors duration-150 hover:bg-neutral-900/60"
            >
              <span className="text-[11px] text-neutral-600">
                Before this month · {shortDate(data.previous_activity.date)}
              </span>
              <span className="mt-1 line-clamp-2 block text-xs leading-5 text-neutral-500">
                {data.previous_activity.excerpt ||
                  "A prior linked activity exists."}
              </span>
            </button>
          )}

          <div className="mt-5 grid gap-6 md:grid-cols-2">
            <div>
              <h4 className="text-xs font-medium text-neutral-400">
                Weekly movement
              </h4>
              {data.weeks.length === 0 ? (
                <p className="mt-3 text-xs text-neutral-600">
                  No movement recorded.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.weeks.map((week) => (
                    <li key={week.week_start}>
                      <div className="flex justify-between gap-3">
                        <span className="text-xs text-neutral-300">
                          {shortDate(week.week_start)} –{" "}
                          {shortDate(week.week_end)}
                        </span>
                        <span className="text-[11px] text-neutral-600">
                          {week.active_days} days
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-500">
                        {week.last_trace_preview ||
                          "Linked activity without a written trace."}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h4 className="text-xs font-medium text-neutral-400">
                Daily traces
              </h4>
              <div className="mt-3 border-y border-neutral-800">
                {data.days.map((day) => (
                  <button
                    key={day.date}
                    type="button"
                    aria-label={`Open ${data.context.name} trace for ${shortDate(day.date)}`}
                    onClick={() => onSelectDate(day.date)}
                    className="grid w-full grid-cols-[4rem_1fr] gap-3 border-b border-neutral-800 px-2 py-2.5 text-left last:border-b-0 hover:bg-neutral-900/60"
                  >
                    <span className="text-xs text-neutral-300">
                      {shortDate(day.date)}
                    </span>
                    <span className="min-w-0 truncate text-xs text-neutral-500">
                      {day.trace_preview ||
                        "Linked activity without a written trace."}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {data.open_threads.length > 0 && (
            <div className="mt-5 border-t border-neutral-800 pt-4">
              <h4 className="text-xs font-medium text-neutral-400">
                Open context threads
              </h4>
              <ul className="mt-2 space-y-1">
                {data.open_threads.slice(0, 5).map((thread) => (
                  <li
                    key={thread.id}
                    className="text-xs leading-5 text-neutral-500"
                  >
                    {thread.content}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

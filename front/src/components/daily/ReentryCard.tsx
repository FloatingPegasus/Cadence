import { useEffect, useState } from "react";

import {
  fetchDayReentry,
  type DailyReentry,
} from "../../api";

interface ReentryCardProps {
  date: string;
  refreshKey: number;
  onSelectDate: (date: string) => void;
}

function shortDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function ReentryCard({
  date,
  refreshKey,
  onSelectDate,
}: ReentryCardProps) {
  const [reentry, setReentry] = useState<DailyReentry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchDayReentry(date)
      .then(setReentry)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load re-entry context",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date, refreshKey]);

  const hasContext =
    reentry?.previous_trace ||
    reentry?.open_threads.length ||
    reentry?.contexts.some((context) => context.last_activity);

  if (!isLoading && !error && !hasContext) return null;

  return (
    <section
      aria-labelledby="reentry-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5 lg:col-span-2"
    >
      <div>
        <h2 id="reentry-title" className="text-sm font-medium text-neutral-200">
          Pick up where you left off
        </h2>
        <p className="mt-1 text-xs text-neutral-500">
          A short look at earlier notes that may help today.
        </p>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">
          Loading prior context…
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      ) : (
        <div className="mt-4 grid gap-5 md:grid-cols-3">
          <div>
            <h3 className="text-xs font-medium text-neutral-400">
              Earlier note
            </h3>
            {reentry?.previous_trace ? (
              <button
                type="button"
                aria-label={`Open prior trace from ${shortDate(reentry.previous_trace.date)}`}
                onClick={() =>
                  onSelectDate(reentry.previous_trace!.date)
                }
                className="mt-2 w-full text-left"
              >
                <span className="text-xs text-violet-300">
                  {shortDate(reentry.previous_trace.date)}
                </span>
                <span className="mt-1 line-clamp-3 block text-xs leading-5 text-neutral-500">
                  {reentry.previous_trace.excerpt}
                </span>
              </button>
            ) : (
              <p className="mt-2 text-xs text-neutral-600">
                No earlier written trace.
              </p>
            )}
          </div>

          <div className="border-neutral-800 md:border-l md:pl-5">
            <h3 className="text-xs font-medium text-neutral-400">
              Open follow-ups
            </h3>
            {reentry?.open_threads.length ? (
              <ul className="mt-2 space-y-2">
                {reentry.open_threads.map((thread) => (
                  <li
                    key={thread.id}
                    className="text-xs leading-5 text-neutral-500"
                  >
                    {thread.content}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-neutral-600">
                Nothing unresolved.
              </p>
            )}
          </div>

          <div className="border-neutral-800 md:border-l md:pl-5">
            <h3 className="text-xs font-medium text-neutral-400">
              Related areas
            </h3>
            {reentry?.contexts.some((context) => context.last_activity) ? (
              <ul className="mt-2 space-y-3">
                {reentry.contexts.map(
                  (context) =>
                    context.last_activity && (
                      <li key={context.id}>
                        <button
                          type="button"
                          aria-label={`Open ${context.name} context from ${shortDate(context.last_activity.date)}`}
                          onClick={() =>
                            onSelectDate(context.last_activity!.date)
                          }
                          className="w-full text-left"
                        >
                          <span className="text-xs text-neutral-300">
                            {context.name}
                          </span>
                          <span className="ml-2 text-[11px] text-neutral-600">
                            {shortDate(context.last_activity.date)}
                          </span>
                          <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-neutral-500">
                            {context.last_activity.excerpt ||
                              "Last linked activity"}
                          </span>
                        </button>
                      </li>
                    ),
                )}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-neutral-600">
                No prior linked activity.
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

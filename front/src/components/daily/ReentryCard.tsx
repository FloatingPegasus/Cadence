import { useEffect, useRef, useState } from "react";

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
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const initial = loadedDate.current !== date;
    if (initial) setIsLoading(true);
    setError(null);
    fetchDayReentry(date)
      .then((result) => {
        if (cancelled) return;
        loadedDate.current = date;
        setReentry(result);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load earlier activity",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, refreshKey]);

  const hasContext =
    reentry?.previous_trace ||
    reentry?.open_threads.length ||
    reentry?.contexts.some((context) => context.last_activity);
  const relatedAreas =
    reentry?.contexts.filter((context) => context.last_activity) ?? [];
  const sectionCount =
    Number(Boolean(reentry?.previous_trace)) +
    Number(Boolean(reentry?.open_threads.length)) +
    Number(relatedAreas.length > 0);

  if (!isLoading && !error && !hasContext) return null;

  return (
    <section
      aria-labelledby="reentry-title"
      className="cadence-surface"
    >
      <h2 id="reentry-title" className="cadence-kicker">
        Pick up where you left off
      </h2>

      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">
          Loading earlier activity...
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      ) : (
        <div
          className={
            sectionCount === 1
              ? "mt-4 grid gap-5"
              : sectionCount === 2
                ? "mt-4 grid gap-5 md:grid-cols-2"
                : "mt-4 grid gap-5 md:grid-cols-3"
          }
        >
          {reentry?.previous_trace && (
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Earlier note
              </h3>
              <button
                type="button"
                aria-label={`Open earlier note from ${shortDate(reentry.previous_trace.date)}`}
                onClick={() => onSelectDate(reentry.previous_trace!.date)}
                className="mt-2 w-full text-left"
              >
                <span className="text-xs text-violet-300">
                  {shortDate(reentry.previous_trace.date)}
                </span>
                <span className="mt-1 line-clamp-3 block text-xs leading-5 text-neutral-500">
                  {reentry.previous_trace.excerpt}
                </span>
              </button>
            </div>
          )}

          {reentry && reentry.open_threads.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Open follow-ups
              </h3>
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
            </div>
          )}

          {relatedAreas.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Related areas
              </h3>
              <ul className="mt-2 space-y-3">
                {relatedAreas.map((context) => (
                  <li key={context.id}>
                    <button
                      type="button"
                      aria-label={`Open ${context.name} from ${shortDate(context.last_activity!.date)}`}
                      onClick={() =>
                        onSelectDate(context.last_activity!.date)
                      }
                      className="w-full text-left"
                    >
                      <span className="text-xs text-neutral-300">
                        {context.name}
                      </span>
                      <span className="ml-2 text-[11px] text-neutral-600">
                        {shortDate(context.last_activity!.date)}
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-neutral-500">
                        {context.last_activity!.excerpt ||
                          "Last linked activity"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

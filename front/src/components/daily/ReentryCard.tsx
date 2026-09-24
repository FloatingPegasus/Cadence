import { useEffect, useRef, useState } from "react";

import {
  fetchDayReentry,
  type DailyReentry,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";
import { formatHourLabel } from "../../time";

interface ReentryCardProps {
  date: string;
  refreshKey: number;
  onSelectDate: (date: string) => void;
  onOpenHour?: (date: string) => void;
  onOpenTask?: () => void;
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
  onOpenHour,
  onOpenTask,
}: ReentryCardProps) {
  const { user } = useAuth();
  const [reentry, setReentry] = useState<DailyReentry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setReentry(null);
      setIsLoading(false);
      return;
    }
    const initial = loadedDate.current === null;
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
  }, [date, refreshKey, user?.id]);

  const hasResume = Boolean(reentry?.last_hour || reentry?.carried_task);
  const hasContext =
    hasResume ||
    reentry?.previous_trace ||
    reentry?.open_tasks.length ||
    reentry?.contexts.some((context) => context.last_activity);
  const relatedAreas =
    reentry?.contexts.filter((context) => context.last_activity) ?? [];
  const sectionCount =
    Number(Boolean(reentry?.previous_trace)) +
    Number(Boolean(reentry?.open_tasks.length)) +
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

      {isLoading && !reentry ? (
        <p className="mt-4 text-sm text-neutral-600">
          Loading earlier activity...
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      ) : hasResume ? (
        <div className="mt-4 grid gap-3">
          {reentry?.last_hour && (
            <button
              type="button"
              onClick={() =>
                (onOpenHour ?? onSelectDate)(reentry.last_hour!.date)
              }
              className="w-full rounded-lg px-1 py-1 text-left hover:bg-neutral-950/40"
            >
              <span className="text-xs text-violet-300">
                {shortDate(reentry.last_hour.date)} ·{" "}
                {formatHourLabel(reentry.last_hour.hour)}
              </span>
              <span className="mt-1 line-clamp-2 block text-sm leading-5 text-neutral-200">
                {reentry.last_hour.content}
              </span>
            </button>
          )}
          {reentry?.carried_task && (
            <button
              type="button"
              onClick={() => onOpenTask?.()}
              className="w-full rounded-lg px-1 py-1 text-left hover:bg-neutral-950/40"
            >
              <span className="text-xs text-violet-300">
                {shortDate(reentry.carried_task.due_date)}
              </span>
              <span className="mt-1 block text-sm text-neutral-100">
                {reentry.carried_task.title}
              </span>
            </button>
          )}
        </div>
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

          {reentry && reentry.open_tasks.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-neutral-400">
                Open tasks
              </h3>
              <ul className="mt-2 space-y-2">
                {reentry.open_tasks.map((task) => (
                  <li
                    key={task.id}
                    className="text-xs leading-5 text-neutral-500"
                  >
                    {task.title}
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

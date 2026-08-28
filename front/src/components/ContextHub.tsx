import { useEffect, useState } from "react";

import {
  fetchContextContinuity,
  type ContextContinuity,
  type ContinuityContext,
} from "../api";

interface ContextHubProps {
  contexts: ContinuityContext[];
  onSelectDate: (date: string) => void;
  refreshKey: number;
  embedded?: boolean;
}

function formatDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function ContextHub({
  contexts,
  onSelectDate,
  refreshKey,
  embedded = false,
}: ContextHubProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [continuity, setContinuity] = useState<ContextContinuity | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (contexts.length === 0) {
      setSelectedId(null);
      setContinuity(null);
      return;
    }
    if (!contexts.some((context) => context.id === selectedId)) {
      setSelectedId(contexts[0].id);
    }
  }, [contexts, selectedId]);

  useEffect(() => {
    if (selectedId == null) return;
    setIsLoading(true);
    setError(null);
    setContinuity(null);
    fetchContextContinuity(selectedId)
      .then(setContinuity)
      .catch((caught) => {
        setContinuity(null);
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load area history",
        );
      })
      .finally(() => setIsLoading(false));
  }, [selectedId, refreshKey]);

  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h2 className="text-sm text-neutral-400">
          Areas
        </h2>
        {contexts.length > 0 && (
          <label className="flex items-center gap-2 text-xs text-neutral-500">
            Area
            <select
              value={selectedId ?? ""}
              onChange={(event) => setSelectedId(Number(event.target.value))}
              className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm text-neutral-300 outline-none focus:border-violet-500/60"
            >
              {contexts.map((context) => (
                <option key={context.id} value={context.id}>
                  {context.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {contexts.length === 0 && (
        <p className="mt-4 text-sm text-neutral-500">
          Add an area in Settings to group related days.
        </p>
      )}
      {isLoading && (
        <p className="mt-4 text-sm text-neutral-600">
          Loading area...
        </p>
      )}
      {error && (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      )}
      {continuity && (
        <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_16rem]">
          <div className="border-y border-neutral-800">
            {continuity.recent_days.length === 0 ? (
              <p className="py-4 text-sm text-neutral-500">
                No days are linked to this area yet.
              </p>
            ) : (
              continuity.recent_days.map((day) => (
                <button
                  key={day.date}
                  type="button"
                  onClick={() => onSelectDate(day.date)}
                  className="grid w-full grid-cols-[5rem_1fr_auto] gap-3 border-b border-neutral-800 px-2 py-3 text-left transition-colors duration-150 last:border-b-0 hover:bg-neutral-900/60"
                >
                  <span className="text-xs font-medium text-neutral-300">
                    {formatDate(day.date)}
                  </span>
                  <span className="min-w-0 truncate text-xs text-neutral-500">
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
            {continuity.open_threads.length === 0 ? (
              <p className="mt-3 text-xs leading-5 text-neutral-600">
                No open follow-ups from this area.
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {continuity.open_threads.map((thread) => (
                  <li key={thread.id}>
                    <p className="text-xs leading-5 text-neutral-400">
                      {thread.content}
                    </p>
                    <p className="mt-1 text-[11px] text-neutral-600">
                      From {formatDate(thread.origin_date)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

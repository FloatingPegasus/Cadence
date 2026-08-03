import { useEffect, useState } from "react";

import {
  fetchClosurePreview,
  updateDayStatus,
  type DayClosurePreview,
} from "../../api";

interface DayClosureCardProps {
  date: string;
  refreshKey: number;
  onChanged: () => void;
}

function plural(count: number, singular: string, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

export default function DayClosureCard({
  date,
  refreshKey,
  onChanged,
}: DayClosureCardProps) {
  const [preview, setPreview] = useState<DayClosurePreview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setIsReviewing(false);
    setError(null);
    fetchClosurePreview(date)
      .then(setPreview)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load the closure review",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date, refreshKey]);

  async function setStatus(status: "open" | "closed") {
    setIsUpdating(true);
    setError(null);
    try {
      await updateDayStatus(date, status);
      setPreview((current) =>
        current ? { ...current, status } : current,
      );
      setIsReviewing(false);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not update the day",
      );
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <section
      aria-labelledby="day-closure-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5 lg:col-span-2"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2
            id="day-closure-title"
            className="text-sm font-medium text-neutral-200"
          >
            Finish the day
          </h2>
          <p className="mt-1 text-xs text-neutral-500">
            Review what you recorded. Nothing is required.
          </p>
        </div>
        {preview?.status === "closed" && (
          <button
            type="button"
            disabled={isUpdating}
            onClick={() => setStatus("open")}
            className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition-colors duration-150 hover:bg-neutral-900 disabled:opacity-50"
          >
            {isUpdating ? "Reopening" : "Reopen day"}
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-600">
          Loading review…
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-400">
          {error}
        </p>
      ) : preview?.status === "closed" ? (
        <p className="mt-4 text-sm text-neutral-400">
          This day is finished. Its notes remain editable and the day can be
          reopened at any time.
        </p>
      ) : preview ? (
        <>
          <dl className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium text-neutral-400">
                Notes
              </dt>
              <dd className="mt-1 text-xs leading-5 text-neutral-500">
                {preview.capture.has_daily_note
                  ? "Daily note saved"
                  : "No daily note"}
                {" · "}
                {plural(
                  preview.capture.conversation_entries,
                  "quick entry",
                  "quick entries",
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-neutral-400">
                Check-in
              </dt>
              <dd className="mt-1 text-xs leading-5 text-neutral-500">
                {plural(preview.capture.checkin_fields, "check-in field")}
                {" · "}
                {plural(
                  preview.capture.completed_habits,
                  "discipline completed",
                  "disciplines completed",
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-neutral-400">
                Summary
              </dt>
              <dd className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-500">
                {preview.summary.exists
                  ? preview.summary.excerpt || "Saved without text"
                  : "Optional · not written"}
              </dd>
            </div>
          </dl>

          <div className="mt-4 border-t border-neutral-800 pt-4">
            <p className="text-xs text-neutral-500">
                {preview.open_thread_count === 0
                ? "No open follow-ups."
                : `${plural(preview.open_thread_count, "follow-up")} will remain visible after closing.`}
            </p>
            {preview.open_threads.length > 0 && (
              <ul className="mt-2 space-y-1">
                {preview.open_threads.map((thread) => (
                  <li
                    key={thread.id}
                    className="text-xs leading-5 text-neutral-600"
                  >
                    {thread.content}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {isReviewing ? (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-800 pt-4">
              <p className="max-w-xl text-xs leading-5 text-neutral-500">
                Finishing does not lock this record or complete its follow-ups.
                You can reopen it whenever you need to add more.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsReviewing(false)}
                  className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900"
                >
                  Keep open
                </button>
                <button
                  type="button"
                  disabled={isUpdating}
                  onClick={() => setStatus("closed")}
                  className="rounded-lg bg-violet-500 px-3 py-1.5 text-xs text-white transition-colors duration-150 hover:bg-violet-400 disabled:opacity-50"
                >
                  {isUpdating ? "Finishing" : "Finish day"}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsReviewing(true)}
              className="mt-5 rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-300 transition-colors duration-150 hover:bg-neutral-900"
            >
              Review and finish
            </button>
          )}
        </>
      ) : null}
    </section>
  );
}

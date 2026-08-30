import { useEffect, useRef, useState } from "react";

import {
  fetchSummary,
  generateSummary,
  updateSummary,
  type DailySummary,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";

interface DailySummaryCardProps {
  date: string;
  refreshKey: number;
  onChanged: () => void;
}

export default function DailySummaryCard({
  date,
  refreshKey,
  onChanged,
}: DailySummaryCardProps) {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const initial = loadedDate.current !== date;
    if (initial) setIsLoading(true);
    setError(null);
    fetchSummary(date)
      .then((dailySummary) => {
        if (cancelled) return;
        loadedDate.current = date;
        setSummary(dailySummary);
        setContent(dailySummary?.content ?? "");
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load the summary",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, refreshKey]);

  async function save() {
    setIsBusy(true);
    setError(null);
    try {
      const saved = await updateSummary(date, content);
      setSummary(saved);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not save the summary",
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function generate() {
    const replaceEdited =
      summary?.is_user_edited === true &&
      window.confirm(
        "Replace your edited summary with a newly generated version?",
      );
    if (summary?.is_user_edited && !replaceEdited) return;

    setIsBusy(true);
    setError(null);
    try {
      const generated = await generateSummary(date, replaceEdited);
      setSummary(generated);
      setContent(generated.content);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not generate the summary",
      );
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <details className="py-2">
      <summary
        id="daily-summary-title"
        className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
      >
        Daily review
      </summary>

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={generate}
          disabled={
            isLoading || isBusy || !user?.ai_processing_consent
          }
          className="rounded-lg border border-violet-500/50 bg-violet-500/5 px-3 py-1.5 text-xs text-violet-300 transition-colors duration-150 hover:bg-violet-500/10 disabled:opacity-40"
        >
          Generate review
        </button>
        <button
          type="button"
          onClick={save}
          disabled={isLoading || isBusy}
          className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 transition-colors duration-200 hover:bg-neutral-700 disabled:opacity-40"
        >
          Save review
        </button>
      </div>

      {!user?.ai_processing_consent && (
        <p className="mt-3 text-xs text-neutral-600">
          Automatic summaries are off. Enable AI in Settings if you want
          Cadence to create one from today’s notes.
        </p>
      )}

      <label
        htmlFor="daily-summary-content"
        className="sr-only"
      >
        Summary
      </label>
      <textarea
        id="daily-summary-content"
        value={content}
        disabled={isLoading}
        onChange={(event) => setContent(event.target.value)}
        placeholder={isLoading ? "Loading review…" : undefined}
        className="mt-4 min-h-32 w-full resize-y rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600 disabled:opacity-60"
      />

      {summary?.is_stale && (
        <p
          role="status"
          className="mt-2 rounded-lg border border-amber-900 bg-amber-950/30 px-3 py-2 text-xs leading-5 text-amber-300"
        >
          Source entries changed after this summary was saved. Save edits to
          make it current, or generate a new draft.
        </p>
      )}
      {summary && (
        <p className="mt-2 text-[11px] text-neutral-600">
          {summary.is_user_edited
            ? "Edited by you"
            : "Generated automatically"}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
    </details>
  );
}

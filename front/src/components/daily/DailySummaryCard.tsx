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
  const { user, aiEnabled } = useAuth();
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setSummary(null);
      setContent("");
      setIsLoading(false);
      return;
    }
    const initial = loadedDate.current === null;
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
  }, [date, refreshKey, user?.id]);

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

  const needsSave =
    content !== (summary?.content ?? "") || summary?.is_stale === true;

  return (
    <details className="py-2">
      <summary
        id="daily-summary-title"
        className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
      >
        Daily review
      </summary>

      <div className="mt-4 flex gap-2">
        {aiEnabled ? (
          <button
            type="button"
            onClick={generate}
            disabled={
              isLoading || isBusy || !user?.ai_processing_consent
            }
            className="cadence-chip cadence-chip-accent sm:text-xs"
          >
            Generate review
          </button>
        ) : null}
        <button
          type="button"
          onClick={save}
          disabled={isLoading || isBusy || !needsSave}
          className={`cadence-chip sm:text-xs ${needsSave ? "cadence-chip-solid" : "cadence-chip-ghost"}`}
        >
          Save review
        </button>
      </div>

      {aiEnabled && !user?.ai_processing_consent && (
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
        className="cadence-field mt-4 min-h-32 resize-none disabled:opacity-60"
      />

      {summary?.is_stale && (
        <p
          role="status"
          className="mt-2 rounded-lg border border-amber-900 bg-amber-950/30 px-3 py-2 text-xs leading-5 text-amber-300"
        >
          {aiEnabled
            ? "Source entries changed after this summary was saved. Save edits to make it current, or generate a new draft."
            : "Source entries changed after this summary was saved. Save edits to make it current."}
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

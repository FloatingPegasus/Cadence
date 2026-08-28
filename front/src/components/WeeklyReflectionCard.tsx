import { useEffect, useState } from "react";

import {
  fetchWeeklyReflection,
  generateWeeklyReflection,
  updateWeeklyReflection,
  type WeeklyReflection,
} from "../api";
import { useAuth } from "../contexts/AuthContext";

interface WeeklyReflectionCardProps {
  anchorDate: string;
  refreshKey: number;
  onChanged: () => void;
}

export default function WeeklyReflectionCard({
  anchorDate,
  refreshKey,
  onChanged,
}: WeeklyReflectionCardProps) {
  const { user } = useAuth();
  const [reflection, setReflection] = useState<WeeklyReflection | null>(null);
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchWeeklyReflection(anchorDate)
      .then((weeklyReflection) => {
        setReflection(weeklyReflection);
        setContent(weeklyReflection?.content ?? "");
      })
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load the weekly review",
        );
      })
      .finally(() => setIsLoading(false));
  }, [anchorDate, refreshKey]);

  async function save() {
    setIsBusy(true);
    setError(null);
    try {
      const saved = await updateWeeklyReflection(anchorDate, content);
      setReflection(saved);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not save the weekly review",
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function generate() {
    const replaceEdited =
      reflection?.is_user_edited === true &&
      window.confirm(
        "Replace your edited weekly review with a generated draft?",
      );
    if (reflection?.is_user_edited && !replaceEdited) return;

    setIsBusy(true);
    setError(null);
    try {
      const generated = await generateWeeklyReflection(
        anchorDate,
        replaceEdited,
      );
      setReflection(generated);
      setContent(generated.content);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not generate the weekly review",
      );
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="weekly-reflection-title"
      className="mt-16"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h3
          id="weekly-reflection-title"
          className="text-sm text-neutral-400"
        >
          Review
        </h3>
        <div className="flex gap-5">
          <button
            type="button"
            onClick={generate}
            disabled={
              isLoading || isBusy || !user?.ai_processing_consent
            }
            className="text-sm text-neutral-500 transition-colors hover:text-neutral-200 disabled:opacity-40"
          >
            Generate
          </button>
          <button
            type="button"
            onClick={save}
            disabled={isLoading || isBusy}
            className="text-sm text-neutral-500 transition-colors hover:text-neutral-200 disabled:opacity-40"
          >
            Save
          </button>
        </div>
      </div>

      <label className="sr-only" htmlFor="weekly-reflection-content">
        Weekly review
      </label>
      <textarea
        id="weekly-reflection-content"
        value={content}
        disabled={isLoading}
        maxLength={30000}
        onChange={(event) => setContent(event.target.value)}
        placeholder={isLoading ? "Loading review..." : ""}
        className="mt-5 min-h-36 w-full resize-y border-0 border-b border-neutral-800 bg-transparent p-0 pb-3 text-base leading-7 text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-500 disabled:opacity-60"
      />

      {reflection?.is_stale && (
        <p
          role="status"
          className="mt-4 text-xs leading-5 text-amber-300"
        >
          The week changed after this review was saved. Save your edits
          to make it current, or generate a new draft.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

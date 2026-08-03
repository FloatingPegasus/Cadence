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
            : "Could not load the weekly reflection",
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
          : "Could not save the weekly reflection",
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function generate() {
    const replaceEdited =
      reflection?.is_user_edited === true &&
      window.confirm(
        "Replace your edited weekly reflection with a generated draft?",
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
          : "Could not generate the weekly reflection",
      );
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="weekly-reflection-title"
      className="mt-6 border-t border-neutral-800 pt-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3
            id="weekly-reflection-title"
            className="text-xs font-medium text-neutral-300"
          >
            Weekly reflection
          </h3>
          <p className="mt-1 text-xs text-neutral-500">
            Your interpretation of the week. Generation is optional.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={generate}
            disabled={
              isLoading || isBusy || !user?.ai_processing_consent
            }
            className="rounded-lg border border-violet-500/50 bg-violet-500/5 px-3 py-1.5 text-xs text-violet-300 transition-colors duration-150 hover:bg-violet-500/10 disabled:opacity-40"
          >
            Generate reflection
          </button>
          <button
            type="button"
            onClick={save}
            disabled={isLoading || isBusy}
            className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:opacity-40"
          >
            Save reflection
          </button>
        </div>
      </div>

      {!user?.ai_processing_consent && (
        <p className="mt-3 text-xs text-neutral-600">
          Automatic writing is off. Write locally or enable it in Settings.
        </p>
      )}

      <label className="sr-only" htmlFor="weekly-reflection-content">
        Weekly reflection
      </label>
      <textarea
        id="weekly-reflection-content"
        value={content}
        disabled={isLoading}
        maxLength={30000}
        onChange={(event) => setContent(event.target.value)}
        placeholder={
          isLoading
            ? "Loading reflection…"
            : "What moved, what created friction, and what should remain visible next week?"
        }
        className="mt-4 min-h-32 w-full resize-y rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600 disabled:opacity-60"
      />

      {reflection?.is_stale && (
        <p
          role="status"
          className="mt-2 rounded-lg border border-amber-900 bg-amber-950/30 px-3 py-2 text-xs leading-5 text-amber-300"
        >
          The week changed after this reflection was saved. Save your edits
          to make it current, or generate a new draft.
        </p>
      )}
      {reflection && (
        <p className="mt-2 text-[11px] text-neutral-600">
          {reflection.is_user_edited
            ? "Manually edited"
            : "Generated automatically"}
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

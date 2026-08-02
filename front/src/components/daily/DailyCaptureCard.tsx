import { useEffect, useState } from "react";

import {
  fetchCheckin,
  fetchDay,
  fetchDayContexts,
  updateCheckin,
  updateDay,
  updateDayContexts,
  type Checkin,
  type ContinuityContext,
} from "../../api";

interface DailyCaptureCardProps {
  date: string;
  contexts: ContinuityContext[];
  onChanged: () => void;
}

const checkinFields: Array<{
  key: keyof Checkin;
  label: string;
  low: string;
  high: string;
}> = [
  {
    key: "energy_level",
    label: "Energy",
    low: "Depleted",
    high: "Strong",
  },
  {
    key: "focus_quality",
    label: "Focus",
    low: "Scattered",
    high: "Clear",
  },
  {
    key: "recovery_quality",
    label: "Recovery",
    low: "Poor",
    high: "Restored",
  },
  {
    key: "reentry_success",
    label: "Re-entry",
    low: "Difficult",
    high: "Easy",
  },
];

export default function DailyCaptureCard({
  date,
  contexts,
  onChanged,
}: DailyCaptureCardProps) {
  const [note, setNote] = useState("");
  const [checkin, setCheckin] = useState<Checkin>({});
  const [attachedContexts, setAttachedContexts] = useState<
    ContinuityContext[]
  >([]);
  const [selectedContextIds, setSelectedContextIds] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([fetchDay(date), fetchCheckin(date)])
      .then(([day, values]) => {
        setNote(day.daily_note);
        setCheckin(values);
      })
      .catch((caught) => {
        setError(
          caught instanceof Error ? caught.message : "Could not load the day",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date]);

  useEffect(() => {
    fetchDayContexts(date)
      .then((dayContexts) => {
        setAttachedContexts(dayContexts);
        setSelectedContextIds(
          dayContexts.map((context) => context.id),
        );
      })
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load contexts",
        );
      });
  }, [date, contexts]);

  async function save() {
    setIsSaving(true);
    setSaved(false);
    setError(null);
    try {
      const [, , updatedContexts] = await Promise.all([
        updateDay(date, note),
        updateCheckin(date, checkin),
        updateDayContexts(date, selectedContextIds),
      ]);
      setAttachedContexts(updatedContexts);
      setSaved(true);
      onChanged();
      window.setTimeout(() => setSaved(false), 1800);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not save the day",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function setNumber(key: keyof Checkin, value: string) {
    setCheckin((current) => ({
      ...current,
      [key]: value === "" ? null : Number(value),
    }));
  }

  function setText(key: keyof Checkin, value: string) {
    setCheckin((current) => ({
      ...current,
      [key]: value === "" ? null : value,
    }));
  }

  function toggleContext(contextId: number) {
    setSelectedContextIds((current) =>
      current.includes(contextId)
        ? current.filter((id) => id !== contextId)
        : [...current, contextId],
    );
  }

  const contextOptions = [
    ...contexts,
    ...attachedContexts.filter(
      (attached) =>
        !contexts.some((context) => context.id === attached.id),
    ),
  ];

  return (
    <section
      aria-labelledby="daily-capture-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5"
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2
            id="daily-capture-title"
            className="text-sm font-medium text-neutral-200"
          >
            Daily continuity
          </h2>
          <p className="mt-1 text-xs text-neutral-500">
            {date} · capture what should not be lost
          </p>
        </div>
        <button
          type="button"
          onClick={save}
          disabled={isLoading || isSaving}
          className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? "Saving" : saved ? "Saved" : "Save day"}
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-neutral-600">Loading day…</p>
      ) : (
        <>
          <label
            htmlFor="daily-note"
            className="mb-1.5 block text-xs text-neutral-500"
          >
            Daily note
          </label>
          <textarea
            id="daily-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What happened, what moved, or what are you returning to?"
            className="min-h-28 w-full resize-y rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
          />

          {contextOptions.length > 0 && (
            <fieldset className="mt-4">
              <legend className="text-xs text-neutral-500">Contexts</legend>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
                {contextOptions.map((context) => (
                  <label
                    key={context.id}
                    className="flex items-center gap-2 text-xs text-neutral-400"
                  >
                    <input
                      type="checkbox"
                      checked={selectedContextIds.includes(context.id)}
                      disabled={context.is_archived}
                      onChange={() => toggleContext(context.id)}
                      className="accent-violet-500"
                    />
                    <span>
                      {context.name}
                      {context.is_archived && " (archived)"}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          <fieldset className="mt-4">
            <legend className="text-xs text-neutral-500">
              Quick check-in
            </legend>
            <div className="mt-2 grid grid-cols-2 gap-3">
              {checkinFields.map(({ key, label, low, high }) => (
                <label key={key} className="text-xs text-neutral-500">
                  {label}
                  <select
                    value={checkin[key] ?? ""}
                    onChange={(event) => setNumber(key, event.target.value)}
                    className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-neutral-600"
                  >
                    <option value="">Not set</option>
                    <option value="1">1 · {low}</option>
                    <option value="2">2</option>
                    <option value="3">3 · Neutral</option>
                    <option value="4">4</option>
                    <option value="5">5 · {high}</option>
                  </select>
                </label>
              ))}
            </div>
          </fieldset>

          <details className="mt-4 border-t border-neutral-800 pt-3">
            <summary className="cursor-pointer text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300">
              Add optional detail
            </summary>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <label className="text-xs text-neutral-500">
                Sleep hours
                <input
                  type="number"
                  min="0"
                  max="24"
                  step="0.25"
                  value={checkin.sleep_hours ?? ""}
                  onChange={(event) =>
                    setNumber("sleep_hours", event.target.value)
                  }
                  className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-neutral-600"
                />
              </label>
              <label className="text-xs text-neutral-500">
                Sleep quality
                <select
                  value={checkin.sleep_quality ?? ""}
                  onChange={(event) =>
                    setNumber("sleep_quality", event.target.value)
                  }
                  className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-neutral-600"
                >
                  <option value="">Not set</option>
                  <option value="1">1 · Poor</option>
                  <option value="2">2</option>
                  <option value="3">3 · Neutral</option>
                  <option value="4">4</option>
                  <option value="5">5 · Restful</option>
                </select>
              </label>
              <label className="text-xs text-neutral-500">
                Emotional state
                <input
                  type="text"
                  maxLength={100}
                  value={checkin.emotional_state ?? ""}
                  onChange={(event) =>
                    setText("emotional_state", event.target.value)
                  }
                  placeholder="A few honest words"
                  className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
                />
              </label>
              <label className="text-xs text-neutral-500">
                Drift minutes
                <input
                  type="number"
                  min="0"
                  max="1440"
                  value={checkin.drift_minutes ?? ""}
                  onChange={(event) =>
                    setNumber("drift_minutes", event.target.value)
                  }
                  className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-neutral-600"
                />
              </label>
              <label className="col-span-2 text-xs text-neutral-500">
                Check-in note
                <textarea
                  value={checkin.notes ?? ""}
                  onChange={(event) => setText("notes", event.target.value)}
                  placeholder="Anything that gives these numbers context"
                  className="mt-1 min-h-20 w-full resize-y rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
                />
              </label>
            </div>
          </details>
        </>
      )}

      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

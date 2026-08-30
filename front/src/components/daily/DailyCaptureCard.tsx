import { useEffect, useRef, useState } from "react";

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
  onChanged: (hasSource?: boolean) => void;
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
    label: "Restarting",
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
  const saveChain = useRef(Promise.resolve());
  const lastNote = useRef("");

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([fetchDay(date), fetchCheckin(date)])
      .then(([day, values]) => {
        setNote(day.daily_note);
        setCheckin(values);
        lastNote.current = day.daily_note;
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
            : "Could not load areas",
        );
      });
  }, [date, contexts]);

  function save(
    nextNote = note,
    nextCheckin = checkin,
    nextContextIds = selectedContextIds,
  ) {
    const task = saveChain.current.catch(() => undefined).then(async () => {
      setIsSaving(true);
      setSaved(false);
      setError(null);
      try {
        const [, , updatedContexts] = await Promise.all([
          updateDay(date, nextNote),
          updateCheckin(date, nextCheckin),
          updateDayContexts(date, nextContextIds),
        ]);
        setAttachedContexts(updatedContexts);
        setSaved(true);
        lastNote.current = nextNote;
        const hasSource =
          nextNote.trim().length > 0 ||
          Object.values(nextCheckin).some(
            (value) => value !== null && value !== undefined && value !== "",
          );
        onChanged(hasSource);
        window.setTimeout(() => setSaved(false), 1800);
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Could not save the day",
        );
      } finally {
        setIsSaving(false);
      }
    });
    saveChain.current = task;
    return task;
  }

  function setNumber(key: keyof Checkin, value: string) {
    const next = {
      ...checkin,
      [key]: value === "" ? null : Number(value),
    };
    setCheckin(next);
    void save(note, next);
  }

  function setText(key: keyof Checkin, value: string) {
    const next = {
      ...checkin,
      [key]: value === "" ? null : value,
    };
    setCheckin(next);
    void save(note, next);
  }

  function toggleContext(contextId: number) {
    const next = selectedContextIds.includes(contextId)
      ? selectedContextIds.filter((id) => id !== contextId)
      : [...selectedContextIds, contextId];
    setSelectedContextIds(next);
    void save(note, checkin, next);
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
    >
      <div className="mb-5 flex items-baseline justify-between gap-4">
        <h2
          id="daily-capture-title"
          className="cadence-kicker"
        >
          Day note
        </h2>
        <span className="text-xs text-neutral-600">
          {isSaving ? "Saving" : saved ? "Saved" : ""}
        </span>
      </div>

      {isLoading ? (
        <p className="text-sm text-neutral-600">Loading day…</p>
      ) : (
        <>
          <textarea
            id="daily-note"
            aria-labelledby="daily-capture-title"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            onBlur={() => {
              if (note === lastNote.current) return;
              void save();
            }}
            className="min-h-36 w-full resize-y border-0 border-b border-neutral-800 bg-transparent p-0 pb-3 text-base leading-7 text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-500"
          />

          {contextOptions.length > 0 && (
            <fieldset className="mt-4">
              <legend className="text-xs text-neutral-500">Areas</legend>
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

          <details className="mt-8">
            <summary className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-300">
              Check-in
            </summary>
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
          </details>

          <details className="mt-6">
            <summary className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-300">
              Add more detail
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
                  className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
                />
              </label>
              <label className="text-xs text-neutral-500">
                Off-track minutes
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

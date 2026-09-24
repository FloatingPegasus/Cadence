import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import {
  fetchCheckin,
  fetchDay,
  fetchDayContexts,
  updateCheckin,
  updateDay,
  updateDayContexts,
  updateDayStatus,
  type Checkin,
  type ContinuityContext,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";

interface CloseDayCardProps {
  date: string;
  contexts: ContinuityContext[];
  onChanged: (hasSource?: boolean) => void;
  children?: ReactNode;
}

interface Scale {
  key: keyof Checkin;
  label: string;
  low: string;
  high: string;
}

const mainScales: Scale[] = [
  { key: "energy_level", label: "Energy", low: "Depleted", high: "Strong" },
  { key: "focus_quality", label: "Focus", low: "Scattered", high: "Clear" },
  { key: "sleep_quality", label: "Sleep", low: "Poor", high: "Restful" },
];

const moreScales: Scale[] = [
  { key: "recovery_quality", label: "Recovery", low: "Poor", high: "Restored" },
  { key: "reentry_success", label: "Restarting", low: "Difficult", high: "Easy" },
];

export default function CloseDayCard({
  date,
  contexts,
  onChanged,
  children,
}: CloseDayCardProps) {
  const { user } = useAuth();
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("open");
  const [checkin, setCheckin] = useState<Checkin>({});
  const [attachedContexts, setAttachedContexts] = useState<
    ContinuityContext[]
  >([]);
  const [selectedContextIds, setSelectedContextIds] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveChain = useRef(Promise.resolve());
  const lastNote = useRef("");
  const lastCheckin = useRef<Checkin>({});
  const loadedDate = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setIsLoading(false);
      return;
    }
    if (loadedDate.current === null) setIsLoading(true);
    setError(null);
    Promise.all([fetchDay(date), fetchCheckin(date)])
      .then(([day, values]) => {
        if (cancelled) return;
        loadedDate.current = date;
        setNote(day.daily_note);
        setStatus(day.status);
        setCheckin(values);
        lastNote.current = day.daily_note;
        lastCheckin.current = values;
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error ? caught.message : "Could not load the day",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, user?.id]);

  useEffect(() => {
    if (!user) return;
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
  }, [date, contexts, user?.id]);

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
        lastCheckin.current = nextCheckin;
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

  async function toggleClosed() {
    const next = status === "closed" ? "open" : "closed";
    setIsClosing(true);
    setError(null);
    try {
      await saveChain.current.catch(() => undefined);
      const day = await updateDayStatus(date, next);
      setStatus(day.status);
      onChanged(day.status === "closed");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not update the day",
      );
    } finally {
      setIsClosing(false);
    }
  }

  function setScale(key: keyof Checkin, value: number | null) {
    const next = { ...checkin, [key]: value };
    setCheckin(next);
    void save(note, next);
  }

  function editCheckin(key: keyof Checkin, value: string, numeric: boolean) {
    setCheckin((current) => ({
      ...current,
      [key]: value === "" ? null : numeric ? Number(value) : value,
    }));
  }

  function commitCheckin(key: keyof Checkin) {
    if ((checkin[key] ?? null) === (lastCheckin.current[key] ?? null)) return;
    void save();
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
  const closed = status === "closed";

  function scaleRow({ key, ...scale }: Scale) {
    return (
      <ScaleRow
        key={key}
        {...scale}
        value={checkin[key] as number | null | undefined}
        onChange={(value) => setScale(key, value)}
      />
    );
  }

  return (
    <section aria-labelledby="close-day-title">
      <div className="flex items-baseline justify-between gap-4">
        <h2
          id="close-day-title"
          className="cadence-mark text-[1.9rem] text-neutral-100"
        >
          {closed ? "Day closed" : "Close the day"}
        </h2>
        <span className="text-xs text-neutral-600">
          {isSaving ? "Saving" : saved ? "Saved" : ""}
        </span>
      </div>

      {isLoading && loadedDate.current === null ? (
        <p className="mt-3 text-sm text-neutral-600">Loading day…</p>
      ) : (
        <>
          <div className="mt-3 grid gap-2">{mainScales.map(scaleRow)}</div>

          <label htmlFor="day-remember" className="sr-only">
            One thing worth remembering
          </label>
          <textarea
            id="day-remember"
            rows={1}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            onBlur={() => {
              if (note === lastNote.current) return;
              void save();
            }}
            placeholder="One thing worth remembering"
            maxLength={20000}
            className="cadence-dashed-field mt-4 resize-none"
          />

          <details className="cadence-fold">
            <summary className="text-sm text-neutral-400 transition-colors duration-150 hover:text-neutral-200">
              More
            </summary>
            <div className="mt-3 grid gap-2">{moreScales.map(scaleRow)}</div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="text-xs text-neutral-500">
                Sleep hours
                <input
                  type="number"
                  min="0"
                  max="24"
                  step="0.25"
                  value={checkin.sleep_hours ?? ""}
                  onChange={(event) =>
                    editCheckin("sleep_hours", event.target.value, true)
                  }
                  onBlur={() => commitCheckin("sleep_hours")}
                  className="cadence-field mt-1"
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
                    editCheckin("drift_minutes", event.target.value, true)
                  }
                  onBlur={() => commitCheckin("drift_minutes")}
                  className="cadence-field mt-1"
                />
              </label>
              <label className="col-span-2 text-xs text-neutral-500">
                Emotional state
                <input
                  type="text"
                  maxLength={100}
                  value={checkin.emotional_state ?? ""}
                  onChange={(event) =>
                    editCheckin("emotional_state", event.target.value, false)
                  }
                  onBlur={() => commitCheckin("emotional_state")}
                  className="cadence-field mt-1"
                />
              </label>
              <label className="col-span-2 text-xs text-neutral-500">
                Check-in note
                <textarea
                  value={checkin.notes ?? ""}
                  onChange={(event) =>
                    editCheckin("notes", event.target.value, false)
                  }
                  onBlur={() => commitCheckin("notes")}
                  className="cadence-field mt-1 min-h-20 resize-none"
                />
              </label>
            </div>
            {contextOptions.length > 0 && (
              <fieldset className="mt-4 mb-2">
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
                        className="accent-done"
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
          </details>

          {children}

          <button
            type="button"
            onClick={() => void toggleClosed()}
            disabled={isClosing}
            className={
              closed
                ? "cadence-chip cadence-chip-ghost mt-4"
                : "cadence-chip cadence-chip-solid mt-4 px-5"
            }
          >
            {closed ? "Reopen" : "Close"}
          </button>
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

function ScaleRow({
  label,
  low,
  high,
  value,
  onChange,
}: Omit<Scale, "key"> & {
  value: number | null | undefined;
  onChange: (value: number | null) => void;
}) {
  const labelId = useId();
  return (
    <div
      role="group"
      aria-labelledby={labelId}
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 sm:justify-start"
    >
      <span id={labelId} className="text-sm text-neutral-400 sm:w-24">
        {label}
      </span>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((step) => (
          <button
            key={step}
            type="button"
            aria-pressed={value === step}
            aria-label={
              step === 1 ? `1, ${low}` : step === 5 ? `5, ${high}` : String(step)
            }
            onClick={() => onChange(value === step ? null : step)}
            className={
              value === step
                ? "cadence-chip cadence-chip-icon cadence-chip-solid"
                : "cadence-chip cadence-chip-icon"
            }
          >
            {step}
          </button>
        ))}
      </div>
    </div>
  );
}

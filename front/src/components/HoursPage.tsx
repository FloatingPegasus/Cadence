import { useEffect, useState, type FormEvent } from "react";

import {
  addLog,
  deleteLog,
  fetchLogs,
  updateLog,
  type LogEntry,
} from "../api";
import { formatHourLabel, todayAsLocalDate } from "../time";
import { useAuth } from "../contexts/AuthContext";

interface HoursPageProps {
  date: string;
  onSelectDate: (date: string) => void;
  onChanged: () => void;
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

function logHour(entry: LogEntry): number {
  return entry.hour ?? new Date(entry.created_at).getHours();
}

function withoutKey(values: Record<string, string>, key: string) {
  const next = { ...values };
  delete next[key];
  return next;
}

export default function HoursPage({
  date,
  onSelectDate,
  onChanged,
}: HoursPageProps) {
  const { user } = useAuth();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState<number | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setDrafts({});
    setAdding(null);
    if (!user) {
      setLogs([]);
      setIsLoading(false);
      return;
    }
    fetchLogs(date)
      .then((rows) => {
        if (!cancelled) setLogs(rows);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error ? caught.message : "Could not load hours",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, user?.id]);

  const currentHour = new Date().getHours();
  const isToday = date === todayAsLocalDate();
  const byHour = new Map<number, LogEntry[]>();
  for (const entry of logs) {
    if (entry.role !== "user") continue;
    const hour = logHour(entry);
    byHour.set(hour, [...(byHour.get(hour) ?? []), entry]);
  }

  async function saveEntry(entry: LogEntry) {
    const key = String(entry.id);
    const content = (drafts[key] ?? entry.content).trim();
    if (savingKey === key || content === entry.content) return;
    setSavingKey(key);
    setError(null);
    try {
      if (content) {
        const saved = await updateLog(date, entry.id, content);
        setLogs((rows) => rows.map((row) => (row.id === entry.id ? saved : row)));
      } else {
        await deleteLog(date, entry.id);
        setLogs((rows) => rows.filter((row) => row.id !== entry.id));
      }
      setDrafts((values) => withoutKey(values, key));
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not save the hour",
      );
    } finally {
      setSavingKey(null);
    }
  }

  async function addToHour(hour: number) {
    const key = `new-${hour}`;
    const content = (drafts[key] ?? "").trim();
    if (savingKey === key) return;
    if (!content) {
      setAdding(null);
      return;
    }
    setSavingKey(key);
    setError(null);
    try {
      const { log: saved } = await addLog(date, content, hour);
      setLogs((rows) => [...rows, saved]);
      setDrafts((values) => withoutKey(values, key));
      setAdding(null);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not save the hour",
      );
    } finally {
      setSavingKey(null);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>, save: () => Promise<void>) {
    event.preventDefault();
    void save();
  }

  const fieldClass =
    "min-h-11 w-full min-w-0 rounded-md border border-transparent bg-transparent px-2 py-2 text-base text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-700 focus:bg-neutral-950 sm:min-h-0 sm:py-1.5 sm:text-sm";

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="cadence-title text-2xl font-medium text-neutral-100">
          Hours
        </h1>
        <label className="text-xs text-neutral-500">
          <span className="sr-only">Day</span>
          <input
            type="date"
            value={date}
            onChange={(event) => onSelectDate(event.target.value)}
            className="cadence-chip min-h-11 px-2 py-2 text-base text-neutral-300 outline-none sm:min-h-0 sm:py-1.5 sm:text-xs"
          />
        </label>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
      <ol className="cadence-surface mt-6">
        {HOURS.map((offset) => {
          const hour = (offset + (user?.day_ends_at ?? 0)) % 24;
          const active = isToday && hour === currentHour;
          const label = formatHourLabel(hour);
          const entries = byHour.get(hour) ?? [];
          const showNew = entries.length === 0 || adding === hour;
          const newKey = `new-${hour}`;
          const busy =
            savingKey === newKey ||
            entries.some((entry) => String(entry.id) === savingKey);
          return (
            <li
              key={hour}
              data-hour={hour}
              aria-busy={busy}
              className="cadence-hours-row"
            >
              <div
                className={
                  active
                    ? "mx-1 grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-start gap-3 rounded-xl bg-violet-500/10 px-4 py-2.5 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto]"
                    : "mx-1 grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-start gap-3 rounded-xl px-4 py-2.5 hover:bg-neutral-950/40 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto]"
                }
              >
                <label
                  htmlFor={`hour-${hour}`}
                  className={
                    active
                      ? "pt-3 text-xs font-medium text-violet-200 sm:pt-2"
                      : "pt-3 text-xs text-neutral-500 sm:pt-2"
                  }
                >
                  {label}
                </label>
                <div className="grid min-w-0 gap-1">
                  {entries.map((entry, index) => (
                    <form
                      key={entry.id}
                      onSubmit={(event) => submit(event, () => saveEntry(entry))}
                    >
                      <input
                        id={index === 0 ? `hour-${hour}` : undefined}
                        aria-label={index === 0 ? undefined : label}
                        value={drafts[String(entry.id)] ?? entry.content}
                        onChange={(event) =>
                          setDrafts((values) => ({
                            ...values,
                            [String(entry.id)]: event.target.value,
                          }))
                        }
                        onBlur={() => void saveEntry(entry)}
                        maxLength={20000}
                        className={fieldClass}
                      />
                    </form>
                  ))}
                  {showNew && (
                    <form onSubmit={(event) => submit(event, () => addToHour(hour))}>
                      <input
                        id={entries.length === 0 ? `hour-${hour}` : undefined}
                        aria-label={entries.length === 0 ? undefined : label}
                        value={drafts[newKey] ?? ""}
                        disabled={isLoading}
                        autoFocus={adding === hour}
                        onChange={(event) =>
                          setDrafts((values) => ({
                            ...values,
                            [newKey]: event.target.value,
                          }))
                        }
                        onBlur={() => void addToHour(hour)}
                        placeholder={active && entries.length === 0 ? "Now" : ""}
                        maxLength={20000}
                        className={fieldClass}
                      />
                    </form>
                  )}
                </div>
                {showNew ? (
                  <span className="w-11 sm:w-[2.15rem]" />
                ) : (
                  <button
                    type="button"
                    aria-label={`Add to ${label}`}
                    onClick={() => setAdding(hour)}
                    className="cadence-chip cadence-chip-icon cadence-chip-ghost"
                  >
                    <svg
                      viewBox="0 0 16 16"
                      className="h-[0.9rem] w-[0.9rem]"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M8 3.5v9M3.5 8h9"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

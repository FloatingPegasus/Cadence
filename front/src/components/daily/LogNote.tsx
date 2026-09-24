import { useEffect, useState, type FormEvent } from "react";

import { addLog, fetchLogs, type LogEntry } from "../../api";
import { useAuth } from "../../contexts/AuthContext";
import { formatHourLabel } from "../../time";

interface LogNoteProps {
  date: string;
  hour: number;
  refreshKey: number;
  onStartFocus: () => void;
  onChanged: () => void;
}

function entryTime(entry: LogEntry) {
  if (entry.hour !== null) return formatHourLabel(entry.hour);
  return new Date(entry.created_at).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function LogNote({
  date,
  hour,
  refreshKey,
  onStartFocus,
  onChanged,
}: LogNoteProps) {
  const { user } = useAuth();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setShowAll(false);
    if (!user) {
      setLogs([]);
      return;
    }
    fetchLogs(date)
      .then((rows) => {
        if (!cancelled) setLogs(rows);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error ? caught.message : "Could not load today's logs",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [date, refreshKey, user?.id]);

  const loggedHours = new Set(
    logs
      .filter((entry) => entry.role === "user" && entry.hour !== null)
      .map((entry) => entry.hour),
  ).size;
  const lastUser = logs.map((entry) => entry.role).lastIndexOf("user");
  const latest = lastUser === -1 ? [] : logs.slice(lastUser);
  const thread = showAll ? logs : latest;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || isSaving) return;
    setIsSaving(true);
    setError(null);
    try {
      const entry = await addLog(date, content, hour);
      setLogs((current) => [...current, entry]);
      setDraft("");
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the log");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section aria-labelledby="log-note-title">
      <div className="flex items-baseline justify-between gap-3">
        <h2
          id="log-note-title"
          className="cadence-mark text-[1.9rem] text-neutral-100"
        >
          <span className="cadence-marker">{formatHourLabel(hour)}</span>
        </h2>
        {loggedHours > 0 ? (
          <span className="text-xs text-neutral-500">
            {loggedHours} {loggedHours === 1 ? "hour" : "hours"} logged
          </span>
        ) : null}
      </div>
      <form onSubmit={submit} className="mt-3 flex items-end gap-2">
        <label htmlFor="log-note-field" className="sr-only">
          What are you doing?
        </label>
        <input
          id="log-note-field"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="What are you doing?"
          maxLength={20000}
          className="cadence-dashed-field min-w-0 flex-1"
        />
        {draft.trim() ? (
          <button
            type="submit"
            disabled={isSaving}
            className="cadence-chip cadence-chip-accent text-xs"
          >
            Log
          </button>
        ) : null}
      </form>
      {thread.length > 0 ? (
        <ol className="mt-4 grid gap-2" aria-label="Today's logs">
          {thread.map((entry) =>
            entry.role === "user" ? (
              <li key={entry.id} className="text-sm text-neutral-300">
                <span className="mr-2 text-xs text-neutral-500">
                  {entryTime(entry)}
                </span>
                {entry.content}
              </li>
            ) : (
              <li
                key={entry.id}
                className="border-l-2 border-violet-400/40 pl-3 text-sm text-neutral-400"
              >
                {entry.content}
              </li>
            ),
          )}
        </ol>
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={onStartFocus}
          className="cadence-chip cadence-chip-solid inline-flex items-center gap-2 px-5"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden="true">
            <path d="M7 4.8v14.4L19 12Z" fill="currentColor" />
          </svg>
          Start focus
        </button>
        {logs.length > latest.length ? (
          <button
            type="button"
            aria-expanded={showAll}
            onClick={() => setShowAll((value) => !value)}
            className="min-h-11 text-sm text-violet-300 hover:text-violet-200"
          >
            {showAll ? "Show less" : "See today"}
          </button>
        ) : null}
      </div>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  addConversationEntry,
  fetchConversation,
  type ConversationEntry,
} from "../../api";

interface QuickThreadCardProps {
  date: string;
  onChanged: () => void;
}

const prompts = [
  "What happened?",
  "What moved forward?",
  "What felt heavy?",
  "What comes next?",
];

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function QuickThreadCard({
  date,
  onChanged,
}: QuickThreadCardProps) {
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entryInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setActivePrompt(null);
    fetchConversation(date)
      .then(setEntries)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load today’s log",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date]);

  async function addEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const entry = await addConversationEntry(date, content);
      setEntries((current) => [...current, entry]);
      setDraft("");
      setActivePrompt(null);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add the entry",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section
      aria-labelledby="daily-log-title"
      className="rounded-lg border border-neutral-800 bg-neutral-900 p-5"
    >
      <h2
        id="daily-log-title"
        className="text-sm font-medium text-neutral-200"
      >
        Today’s log
      </h2>

      <div className="mt-4 max-h-64 overflow-y-auto">
        {isLoading ? (
          <p className="text-sm text-neutral-600">Loading today’s log…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-neutral-600">
            Nothing logged yet.
          </p>
        ) : (
          <ol className="space-y-2">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="flex gap-3 rounded-lg bg-neutral-900 px-3 py-2 text-sm text-neutral-300"
              >
                <time
                  dateTime={entry.created_at}
                  className="w-16 shrink-0 pt-0.5 text-[11px] text-neutral-600"
                >
                  {formatTime(entry.created_at)}
                </time>
                <span className="min-w-0">{entry.content}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <fieldset className="mt-4">
        <legend className="sr-only">Optional prompts</legend>
        <div className="flex flex-wrap gap-2">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              aria-pressed={activePrompt === prompt}
              onClick={() => {
                setActivePrompt((current) =>
                  current === prompt ? null : prompt,
                );
                entryInput.current?.focus();
              }}
              className={
                activePrompt === prompt
                  ? "rounded border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200"
                  : "rounded border border-neutral-800 px-2.5 py-1.5 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              }
            >
              {prompt}
            </button>
          ))}
        </div>
      </fieldset>

      <form onSubmit={addEntry} className="mt-3">
        <label
          className="mb-1.5 block text-xs text-neutral-500"
          htmlFor="quick-thread-entry"
        >
          {activePrompt ?? "Add a moment"}
        </label>
        <div className="flex gap-2">
          <input
            ref={entryInput}
            id="quick-thread-entry"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              activePrompt
                ? "Write as much or as little as you need"
                : "What happened just now?"
            }
            className="min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
          />
          <button
            type="submit"
            disabled={isSubmitting || draft.trim().length === 0}
            className="rounded-lg border border-neutral-800 px-3 py-2 text-xs text-neutral-300 transition-colors duration-150 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Saving" : "Log"}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

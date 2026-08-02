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
  "What are you returning to?",
];

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
            : "Could not load the thread",
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
      aria-labelledby="quick-thread-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5"
    >
      <h2
        id="quick-thread-title"
        className="text-sm font-medium text-neutral-200"
      >
        Quick thread
      </h2>
      <p className="mt-1 text-xs text-neutral-500">
        Capture a fragment now; structure can come later.
      </p>

      <div className="mt-4 max-h-52 overflow-y-auto">
        {isLoading ? (
          <p className="text-sm text-neutral-600">Loading thread…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-neutral-600">
            A sentence is enough. Leave a trace for your future self.
          </p>
        ) : (
          <ol className="space-y-3">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="rounded-lg bg-neutral-900 px-3 py-2 text-sm text-neutral-300"
              >
                {entry.content}
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
          {activePrompt ?? "Quick note"}
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
                : "Add a quick note"
            }
            className="min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
          />
          <button
            type="submit"
            disabled={isSubmitting || draft.trim().length === 0}
            className="rounded-lg border border-neutral-800 px-3 py-2 text-xs text-neutral-300 transition-colors duration-150 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Adding" : "Add"}
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

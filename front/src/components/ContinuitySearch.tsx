import { useState, type FormEvent } from "react";

import {
  searchContinuity,
  type ContinuityContext,
  type ContinuitySearchResponse,
  type ContinuitySearchSource,
} from "../api";

interface ContinuitySearchProps {
  contexts: ContinuityContext[];
  onSelectDate: (date: string) => void;
  embedded?: boolean;
}

const sourceOptions: Array<{
  value: ContinuitySearchSource;
  label: string;
}> = [
  { value: "all", label: "Everything" },
  { value: "notes", label: "Daily notes" },
  { value: "conversation", label: "Log entries" },
  { value: "summaries", label: "Summaries" },
  { value: "threads", label: "Follow-ups" },
  { value: "weekly_reflections", label: "Weekly reviews" },
];

function formatDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ContinuitySearch({
  contexts,
  onSelectDate,
  embedded = false,
}: ContinuitySearchProps) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<ContinuitySearchSource>("all");
  const [contextId, setContextId] = useState<number | null>(null);
  const [response, setResponse] =
    useState<ContinuitySearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized.length < 2) return;

    setIsSearching(true);
    setError(null);
    try {
      setResponse(
        await searchContinuity(
          normalized,
          source,
          contextId ?? undefined,
        ),
      );
    } catch (searchError) {
      setError(
        searchError instanceof Error
          ? searchError.message
          : "Search could not be completed",
      );
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <section>
      <div>
        <h2 className="text-sm text-neutral-400">
          Search
        </h2>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_9rem_10rem_auto]"
      >
        <label className="sr-only" htmlFor="continuity-search-query">
          Search history
        </label>
        <input
          id="continuity-search-query"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search your record"
          className="min-w-0 rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 outline-none transition-colors duration-150 placeholder:text-neutral-600 focus:border-violet-500/60"
        />
        <label className="sr-only" htmlFor="continuity-search-source">
          Search source
        </label>
        <select
          id="continuity-search-source"
          value={source}
          onChange={(event) => {
            const nextSource =
              event.target.value as ContinuitySearchSource;
            setSource(nextSource);
            if (nextSource === "weekly_reflections") {
              setContextId(null);
            }
          }}
          className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-400 outline-none transition-colors duration-150 focus:border-violet-500/60"
        >
          {sourceOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="continuity-search-context">
          Search area
        </label>
        <select
          id="continuity-search-context"
          value={contextId ?? ""}
          disabled={source === "weekly_reflections"}
          onChange={(event) =>
            setContextId(
              event.target.value ? Number(event.target.value) : null,
            )
          }
          className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-400 outline-none transition-colors duration-150 focus:border-violet-500/60"
        >
          <option value="">Every area</option>
          {contexts.map((context) => (
            <option key={context.id} value={context.id}>
              {context.name}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={query.trim().length < 2 || isSearching}
          className="rounded-lg border border-violet-500/60 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-300 transition-colors duration-150 hover:bg-violet-500/15 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-neutral-900 disabled:text-neutral-600"
        >
          {isSearching ? "Searching" : "Search"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {error}
        </p>
      )}

      {response && (
        <div className="mt-4 border-y border-neutral-800">
          {response.results.length === 0 ? (
            <p className="py-4 text-sm text-neutral-500">
              No matching history found.
            </p>
          ) : (
            response.results.map((result) => (
              <button
                key={`${result.source}-${result.source_id}`}
                type="button"
                onClick={() => onSelectDate(result.date)}
                className="grid w-full gap-1 border-b border-neutral-800 px-2 py-3 text-left transition-colors duration-150 last:border-b-0 hover:bg-neutral-900/60"
              >
                <span className="flex items-center justify-between gap-4">
                  <span className="text-xs font-medium text-neutral-300">
                    {result.title}
                  </span>
                  <span className="text-xs text-neutral-600">
                    {formatDate(result.date)}
                  </span>
                </span>
                <span className="text-xs leading-5 text-neutral-500">
                  {result.excerpt}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </section>
  );
}

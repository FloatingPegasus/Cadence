import { useEffect, useState, type FormEvent } from "react";

import {
  createCarryForward,
  fetchCarryForward,
  updateCarryForwardStatus,
  type CarryForwardItem,
} from "../../api";

interface CarryForwardCardProps {
  date: string;
  onChanged: () => void;
}

export default function CarryForwardCard({
  date,
  onChanged,
}: CarryForwardCardProps) {
  const [items, setItems] = useState<CarryForwardItem[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchCarryForward(date)
      .then(setItems)
      .catch((caught) => {
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load carry-forward threads",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date]);

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const item = await createCarryForward(date, content);
      setItems((current) => [...current, item]);
      setDraft("");
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add the thread",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function resolve(
    itemId: number,
    status: CarryForwardItem["status"],
  ) {
    setError(null);
    try {
      const updated = await updateCarryForwardStatus(date, itemId, status);
      setItems((current) =>
        current.map((item) => (item.id === itemId ? updated : item)),
      );
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not update the thread",
      );
    }
  }

  return (
    <section
      aria-labelledby="carry-forward-title"
      className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-5 lg:col-span-2"
    >
      <h2
        id="carry-forward-title"
        className="text-sm font-medium text-neutral-200"
      >
        Carry forward
      </h2>
      <p className="mt-1 text-xs text-neutral-500">
        Threads stay visible until completed or released.
      </p>

      <form onSubmit={addItem} className="mt-4 flex gap-2">
        <label className="sr-only" htmlFor="carry-forward-entry">
          Add a carry-forward thread
        </label>
        <input
          id="carry-forward-entry"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="What should remain visible tomorrow?"
          maxLength={2000}
          className="min-w-0 flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
        />
        <button
          disabled={isSubmitting || draft.trim().length === 0}
          className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Adding" : "Carry"}
        </button>
      </form>

      <div className="mt-4">
        {isLoading ? (
          <p className="text-xs text-neutral-600">Loading threads…</p>
        ) : items.length === 0 ? (
          <p className="text-xs text-neutral-600">
            Nothing is asking to be carried forward.
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                className={
                  item.status === "open"
                    ? "flex items-center justify-between gap-4 rounded-lg bg-neutral-900 px-3 py-2"
                    : "flex items-center justify-between gap-4 rounded-lg px-3 py-2 opacity-50"
                }
              >
                <div>
                  <p className="text-sm text-neutral-300">{item.content}</p>
                  <p className="mt-0.5 text-[11px] text-neutral-600">
                    {item.origin_date === date
                      ? "Added today"
                      : `Carried from ${item.origin_date}`}
                    {item.status !== "open" && ` · ${item.status}`}
                  </p>
                </div>
                {item.status === "open" && (
                  <div className="flex shrink-0 gap-3">
                    <button
                      type="button"
                      onClick={() => resolve(item.id, "completed")}
                      className="text-xs text-neutral-400 hover:text-neutral-200"
                    >
                      Done
                    </button>
                    <button
                      type="button"
                      onClick={() => resolve(item.id, "released")}
                      className="text-xs text-neutral-600 hover:text-neutral-400"
                    >
                      Release
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

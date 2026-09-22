import { useEffect, useState, type FormEvent } from "react";

import {
  createCarryForward,
  fetchCarryForward,
  updateCarryForwardStatus,
  type CarryForwardItem,
} from "../../api";
import { useAuth } from "../../contexts/AuthContext";

interface CarryForwardCardProps {
  date: string;
  onChanged: () => void;
}

export default function CarryForwardCard({
  date,
  onChanged,
}: CarryForwardCardProps) {
  const { user } = useAuth();
  const [items, setItems] = useState<CarryForwardItem[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!user) {
      setItems([]);
      setIsLoading(false);
      return;
    }
    fetchCarryForward(date)
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load follow-ups",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, user?.id]);

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
        caught instanceof Error ? caught.message : "Could not add the follow-up",
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
          : "Could not update the follow-up",
      );
    }
  }

  return (
    <details className="py-2">
      <summary className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200">
        Follow-ups
      </summary>
      <form onSubmit={addItem} className="mt-4 flex gap-2">
        <label className="sr-only" htmlFor="carry-forward-entry">
          Add a follow-up
        </label>
        <input
          id="carry-forward-entry"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={2000}
          className="cadence-field min-w-0 flex-1"
        />
        <button
          disabled={isSubmitting || draft.trim().length === 0}
          className={`cadence-chip min-h-11 px-3.5 sm:text-xs ${draft.trim() ? "cadence-chip-solid" : "cadence-chip-ghost"}`}
        >
          {isSubmitting ? "Adding" : "Add"}
        </button>
      </form>

      <div className="mt-4">
        {isLoading && items.length === 0 ? (
          <p className="text-xs text-neutral-600">Loading follow-ups…</p>
        ) : items.length === 0 ? null : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                className={
                  item.status === "open"
                    ? "flex items-center justify-between gap-4 rounded-lg bg-neutral-950 px-3 py-2"
                    : "flex items-center justify-between gap-4 rounded-lg px-3 py-2 opacity-50"
                }
              >
                <div>
                  <p className="text-sm text-neutral-300">{item.content}</p>
                  <p className="mt-0.5 text-[11px] text-neutral-600">
                    {item.origin_date === date
                      ? "Added today"
                      : `From ${item.origin_date}`}
                    {item.status !== "open" &&
                      ` · ${item.status === "completed" ? "Completed" : "Dismissed"}`}
                  </p>
                </div>
                {item.status === "open" && (
                  <div className="flex shrink-0 gap-3">
                    <button
                      type="button"
                      onClick={() => resolve(item.id, "completed")}
                      className="text-xs text-neutral-400 hover:text-neutral-200"
                    >
                      Complete
                    </button>
                    <button
                      type="button"
                      onClick={() => resolve(item.id, "released")}
                      className="text-xs text-neutral-600 hover:text-neutral-400"
                    >
                      Dismiss
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
    </details>
  );
}

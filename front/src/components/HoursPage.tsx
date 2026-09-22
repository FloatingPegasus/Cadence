import { useEffect, useState, type FormEvent } from "react";

import {
  fetchHourLog,
  upsertHourLog,
  type HourSlot,
} from "../api";
import { formatHourLabel, todayAsLocalDate } from "../time";
import { useAuth } from "../contexts/AuthContext";

interface HoursPageProps {
  date: string;
  onSelectDate: (date: string) => void;
  onChanged: () => void;
}

export default function HoursPage({
  date,
  onSelectDate,
  onChanged,
}: HoursPageProps) {
  const { user } = useAuth();
  const [slots, setSlots] = useState<HourSlot[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [savingHour, setSavingHour] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (!user) {
      setSlots([]);
      setDrafts({});
      setIsLoading(false);
      return;
    }
    fetchHourLog(date)
      .then((rows) => {
        if (cancelled) return;
        setSlots(rows);
        setDrafts(
          Object.fromEntries(rows.map((row) => [row.hour, row.content])),
        );
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

  async function saveHour(hour: number) {
    const content = (drafts[hour] ?? "").trim();
    const current = slots.find((slot) => slot.hour === hour)?.content ?? "";
    if (content === current) return;
    setSavingHour(hour);
    setError(null);
    try {
      const saved = await upsertHourLog(date, hour, content);
      setSlots((rows) =>
        rows.map((row) => (row.hour === hour ? saved : row)),
      );
      setDrafts((values) => ({ ...values, [hour]: saved.content }));
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not save the hour",
      );
    } finally {
      setSavingHour(null);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>, hour: number) {
    event.preventDefault();
    void saveHour(hour);
  }

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
        {(slots.length ? slots : Array.from({ length: 24 }, (_, hour) => ({
          hour,
          content: "",
        }))).map((slot) => {
          const active = isToday && slot.hour === currentHour;
          return (
            <li key={slot.hour} data-hour={slot.hour} className="cadence-hours-row">
              <form
                onSubmit={(event) => handleSubmit(event, slot.hour)}
                aria-busy={savingHour === slot.hour}
                className={
                  active
                    ? "mx-1 grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-3 rounded-xl bg-violet-500/10 px-4 py-2.5 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto]"
                    : "mx-1 grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-3 rounded-xl px-4 py-2.5 hover:bg-neutral-950/40 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto]"
                }
              >
                <label
                  htmlFor={`hour-${slot.hour}`}
                  className={
                    active
                      ? "text-xs font-medium text-violet-200"
                      : "text-xs text-neutral-500"
                  }
                >
                  {formatHourLabel(slot.hour)}
                </label>
                <input
                  id={`hour-${slot.hour}`}
                  value={drafts[slot.hour] ?? ""}
                  disabled={isLoading}
                  onChange={(event) =>
                    setDrafts((values) => ({
                      ...values,
                      [slot.hour]: event.target.value,
                    }))
                  }
                  onBlur={() => void saveHour(slot.hour)}
                  placeholder={active ? "Now" : ""}
                  maxLength={2000}
                  className="min-h-11 min-w-0 rounded-md border border-transparent bg-transparent px-2 py-2 text-base text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-700 focus:bg-neutral-950 sm:min-h-0 sm:py-1.5 sm:text-sm"
                />
                <span className="hidden w-12 text-right text-[11px] text-neutral-600 sm:block">
                  {savingHour === slot.hour ? "Saving" : ""}
                </span>
              </form>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

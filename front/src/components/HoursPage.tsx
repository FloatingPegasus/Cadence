import { useEffect, useState, type FormEvent } from "react";

import {
  fetchHourLog,
  upsertHourLog,
  type HourSlot,
} from "../api";
import { formatHourLabel, todayAsLocalDate } from "../time";

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
  const [slots, setSlots] = useState<HourSlot[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [savingHour, setSavingHour] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const currentHour = new Date().getHours();
  const isToday = date === todayAsLocalDate();

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchHourLog(date)
      .then((rows) => {
        setSlots(rows);
        setDrafts(
          Object.fromEntries(rows.map((row) => [row.hour, row.content])),
        );
      })
      .catch((caught) => {
        setError(
          caught instanceof Error ? caught.message : "Could not load hours",
        );
      })
      .finally(() => setIsLoading(false));
  }, [date]);

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

  const filled = slots.filter((slot) => slot.content.trim()).length;

  return (
    <div className="cadence-enter">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-medium text-neutral-100">Hours</h1>
        <label className="text-xs text-neutral-500">
          Day
          <input
            type="date"
            value={date}
            onChange={(event) => onSelectDate(event.target.value)}
            className="ml-2 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-300 outline-none transition-colors duration-200 focus:border-neutral-600"
          />
        </label>
      </div>
      <p className="mt-2 text-xs text-neutral-500">
        {isLoading
          ? "Loading hours…"
          : filled === 0
            ? "Log what you did each hour."
            : `${filled} hour${filled === 1 ? "" : "s"} logged`}
      </p>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
      <ol className="mt-6 space-y-1.5">
        {(slots.length ? slots : Array.from({ length: 24 }, (_, hour) => ({
          hour,
          content: "",
        }))).map((slot) => {
          const active = isToday && slot.hour === currentHour;
          return (
            <li key={slot.hour}>
              <form
                onSubmit={(event) => handleSubmit(event, slot.hour)}
                className={
                  active
                    ? "grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2"
                    : "grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-200 hover:bg-neutral-900/70"
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
                  placeholder={active ? "This hour" : ""}
                  maxLength={2000}
                  className="min-w-0 rounded-md border border-transparent bg-transparent px-2 py-1.5 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-700 focus:bg-neutral-950"
                />
                <span className="w-12 text-right text-[11px] text-neutral-600">
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

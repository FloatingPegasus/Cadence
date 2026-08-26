import { useEffect, useState } from "react";

import {
  fetchDisciplineMonthlyContinuity,
  type DisciplineMonthlyContinuity,
} from "../api";

interface DisciplineContinuityProps {
  disciplineId: number;
  month: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
  refreshKey: number;
  onClose: () => void;
}

function shortDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function DisciplineContinuity({
  disciplineId,
  month,
  selectedDate,
  onSelectDate,
  refreshKey,
  onClose,
}: DisciplineContinuityProps) {
  const [data, setData] = useState<DisciplineMonthlyContinuity | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    fetchDisciplineMonthlyContinuity(disciplineId, month)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "Could not load habit history");
        }
      });
    return () => {
      active = false;
    };
  }, [disciplineId, month, refreshKey]);

  return (
    <section className="mt-6 border border-neutral-800 bg-neutral-950/40 px-4 py-4" aria-labelledby="discipline-continuity-title">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-neutral-500">Habit history</p>
          <h2 id="discipline-continuity-title" className="mt-1 text-base font-medium text-neutral-100">
            {data?.discipline.name ?? "Loading habit"}
          </h2>
        </div>
        <button type="button" onClick={onClose} className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400">
          Close
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
      {!data && !error && <p className="mt-4 text-sm text-neutral-500">Loading history...</p>}
      {data && (
        <>
          <dl className="mt-5 grid grid-cols-3 gap-3 border-y border-neutral-800 py-3 text-sm">
            <div><dt className="text-neutral-500">Completed days</dt><dd className="mt-1 text-neutral-100">{data.totals.completed_days}</dd></div>
            <div><dt className="text-neutral-500">Days with notes</dt><dd className="mt-1 text-neutral-100">{data.totals.linked_trace_days}</dd></div>
            <div><dt className="text-neutral-500">Areas</dt><dd className="mt-1 text-neutral-100">{data.totals.contexts}</dd></div>
          </dl>

          {data.previous_completion && (
            <button type="button" onClick={() => onSelectDate(data.previous_completion!.date)} className="mt-4 text-left text-sm text-neutral-400 transition-colors duration-150 hover:text-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400">
              Previous completion · {shortDate(data.previous_completion.date)}
              {data.previous_completion.excerpt && <span className="mt-1 block text-neutral-500">{data.previous_completion.excerpt}</span>}
            </button>
          )}

          <div className="mt-5 space-y-2">
            {data.days.map((day) => (
              <button key={day.date} type="button" onClick={() => onSelectDate(day.date)} aria-current={selectedDate === day.date ? "date" : undefined} className="block w-full border-b border-neutral-800/70 py-2 text-left transition-colors duration-150 hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400">
                <span className="flex items-baseline justify-between gap-3">
                  <span className="text-sm text-neutral-200">{shortDate(day.date)}</span>
                  <span className="text-xs text-neutral-600">{day.conversation_entries} log {day.conversation_entries === 1 ? "entry" : "entries"}</span>
                </span>
                {day.trace_preview && <span className="mt-1 block text-sm text-neutral-500">{day.trace_preview}</span>}
                {day.contexts.length > 0 && <span className="mt-1 block text-xs text-neutral-600">{day.contexts.map((context) => context.name).join(" · ")}</span>}
              </button>
            ))}
            {data.days.length === 0 && <p className="text-sm text-neutral-500">No completion days in this month.</p>}
          </div>

          {data.contexts.length > 0 && (
            <div className="mt-5 border-t border-neutral-800 pt-4">
              <p className="text-xs uppercase tracking-wider text-neutral-500">Linked areas</p>
              <ul className="mt-2 space-y-1 text-sm text-neutral-400">
                {data.contexts.map((context) => <li key={context.id}>{context.name} <span className="text-neutral-600">· {context.completed_days} completion {context.completed_days === 1 ? "day" : "days"}</span></li>)}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default DisciplineContinuity;

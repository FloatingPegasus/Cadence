import { useEffect, useState } from "react";

import {
  fetchContinuityPatterns,
  type ContinuityPatterns as PatternData,
} from "../api";

interface ContinuityPatternsProps {
  anchorDate: string;
  refreshKey: number;
}

function shortWeek(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function ContinuityPatterns({
  anchorDate,
  refreshKey,
}: ContinuityPatternsProps) {
  const [data, setData] = useState<PatternData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    fetchContinuityPatterns(anchorDate)
      .then(setData)
      .catch((caught) => {
        setError(
          caught instanceof Error ? caught.message : "Could not load patterns",
        );
      });
  }, [anchorDate, refreshKey]);

  if (error) return <p role="alert" className="pt-4 text-xs text-red-400">{error}</p>;
  if (!data) return <p className="pt-4 text-sm text-neutral-600">Loading patterns…</p>;

  return (
    <section className="pt-4" aria-labelledby="patterns-title">
      <div>
        <h2 id="patterns-title" className="text-sm font-medium text-neutral-200">
          Recorded patterns
        </h2>
        <p className="mt-1 text-xs text-neutral-500">{data.interpretation}</p>
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-3">
        {data.observations.map((observation) => (
          <article key={observation.kind} className="border-t border-neutral-800 pt-3">
            <h3 className="text-xs font-medium text-neutral-300">{observation.title}</h3>
            <p className="mt-2 text-sm leading-6 text-neutral-500">{observation.body}</p>
          </article>
        ))}
      </div>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="text-neutral-600">
            <tr>
              <th className="border-b border-neutral-800 py-2 font-medium">Week</th>
              <th className="border-b border-neutral-800 py-2 font-medium">Recorded days</th>
              <th className="border-b border-neutral-800 py-2 font-medium">Completions</th>
              <th className="border-b border-neutral-800 py-2 font-medium">Energy</th>
              <th className="border-b border-neutral-800 py-2 font-medium">Focus</th>
            </tr>
          </thead>
          <tbody className="text-neutral-400">
            {data.weekly.map((week) => (
              <tr key={week.week_start}>
                <td className="border-b border-neutral-800/60 py-2">{shortWeek(week.week_start)}</td>
                <td className="border-b border-neutral-800/60 py-2">{week.active_days}</td>
                <td className="border-b border-neutral-800/60 py-2">{week.habit_completions}</td>
                <td className="border-b border-neutral-800/60 py-2">{week.average_energy ?? "–"}</td>
                <td className="border-b border-neutral-800/60 py-2">{week.average_focus ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

import { useState } from "react";

import { useAuth } from "../contexts/AuthContext";
import { formatHourLabel } from "../time";

const BOUNDARIES = Array.from({ length: 13 }, (_, hour) => hour);

export default function DaySettings() {
  const { user, updateDaySettings } = useAuth();
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;
  const current = { day_ends_at: user.day_ends_at, auto_close: user.auto_close };

  async function save(next: typeof current) {
    setError(null);
    try {
      await updateDaySettings(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save");
    }
  }

  return (
    <section aria-labelledby="day-settings-title">
      <h2 id="day-settings-title" className="cadence-kicker">
        Your day
      </h2>
      <div className="mt-4 grid gap-3">
        <label className="flex items-center justify-between gap-3 text-sm text-neutral-300">
          Day ends at
          <select
            value={current.day_ends_at}
            onChange={(event) =>
              void save({ ...current, day_ends_at: Number(event.target.value) })
            }
            className="cadence-chip cadence-chip-select"
          >
            {BOUNDARIES.map((hour) => (
              <option key={hour} value={hour}>
                {formatHourLabel(hour)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-h-11 items-center gap-3 text-sm text-neutral-300">
          <input
            type="checkbox"
            checked={current.auto_close}
            onChange={(event) =>
              void save({ ...current, auto_close: event.target.checked })
            }
            className="accent-done"
          />
          Close past days by themselves
        </label>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}

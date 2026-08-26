interface HabitGridProps {
  habits: { id: number; name: string; is_archived: boolean }[];
  days: number[];
  month: string;
  lookup: Record<string, boolean>;
  onToggle: (habitId: number, dateStr: string, newVal: string) => void;
  selectedDate: string | null;
  onSelectDate: (dateStr: string) => void;
  onSelectHabit?: (habitId: number) => void;
}

function HabitGrid({ habits, days, month, lookup, onToggle, selectedDate, onSelectDate, onSelectHabit }: HabitGridProps) {
  function dateStr(day: number) {
    return `${month}-${String(day).padStart(2, "0")}`;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-3 py-2.5 border-b border-neutral-800 w-28">
              Habit
            </th>
            {days.map((d) => (
              <th
                key={d}
                className="text-center text-xs font-medium text-neutral-500 uppercase tracking-wider px-2 py-2.5 border-b border-neutral-800 w-8"
              >
                <button
                  onClick={() => onSelectDate(dateStr(d))}
                  title={`Open ${dateStr(d)}`}
                  className={
                    selectedDate === dateStr(d)
                      ? "text-violet-300"
                      : "hover:text-neutral-200"
                  }
                >
                  {d}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {habits.map((h) => (
            <tr key={h.id} className="group">
              <td className="text-sm text-neutral-300 px-3 py-2.5 border-b border-neutral-800/60">
                {onSelectHabit ? (
                  <button
                    type="button"
                    className="text-left transition-colors duration-150 hover:text-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400"
                    aria-label={`Open ${h.name} history`}
                    onClick={() => onSelectHabit(h.id)}
                  >
                    {h.name}
                  </button>
                ) : (
                  h.name
                )}
                {h.is_archived && (
                  <span className="ml-2 text-[10px] text-neutral-600">
                    archived
                  </span>
                )}
              </td>
              {days.map((d) => {
                const key = `${h.id}-${dateStr(d)}`;
                const active = lookup[key] === true;
                return (
                  <td
                    key={d}
                    className={
                      selectedDate === dateStr(d)
                        ? "border-b border-neutral-800/60 bg-violet-500/20 text-center text-xs font-medium text-violet-300 ring-1 ring-inset ring-violet-400/50"
                        : active
                        ? "border-b border-neutral-800/60 bg-neutral-800 text-center text-xs font-medium text-neutral-200"
                        : "border-b border-neutral-800/60 text-center text-xs text-neutral-600"
                    }
                  >
                    <button
                      type="button"
                      aria-pressed={active}
                      aria-label={`${h.name} on ${dateStr(d)}: ${
                        active ? "completed" : "not completed"
                      }${h.is_archived ? ", archived" : ""}`}
                      onClick={() => {
                        onSelectDate(dateStr(d));
                        if (!h.is_archived) {
                          onToggle(h.id, dateStr(d), active ? "0" : "1");
                        }
                      }}
                      className="w-full px-2 py-2.5 transition-colors duration-150 hover:bg-neutral-700/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400"
                    >
                      {active ? "✓" : "·"}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default HabitGrid;

import { todayAsLocalDate } from "../time";

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

const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function HabitGrid({
  habits,
  days,
  month,
  lookup,
  onToggle,
  selectedDate,
  onSelectDate,
  onSelectHabit,
}: HabitGridProps) {
  const [year, monthNumber] = month.split("-").map(Number);
  const leading = new Date(year, monthNumber - 1, 1).getDay();
  const lastDay = new Date(year, monthNumber, 0).getDate();
  const available = new Set(days);
  const today = todayAsLocalDate();
  const visibleHabits = habits.filter((habit) => !habit.is_archived);
  const listedHabits = visibleHabits.length > 0 ? visibleHabits : habits;

  function dateStr(day: number) {
    return `${month}-${String(day).padStart(2, "0")}`;
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-y-3">
        {weekdays.map((day) => (
          <div
            key={day}
            className="pb-2 text-center text-[11px] text-neutral-500"
          >
            {day}
          </div>
        ))}
        {Array.from({ length: leading }, (_, index) => (
          <div key={`pad-${index}`} />
        ))}
        {Array.from({ length: lastDay }, (_, index) => {
          const day = index + 1;
          const date = dateStr(day);
          const enabled = available.has(day);
          const selected = selectedDate === date;
          const isToday = date === today;
          const completed = listedHabits.filter(
            (habit) => lookup[`${habit.id}-${date}`] === true,
          ).length;
          return (
            <div
              key={day}
              className={
                selected
                  ? "rounded-2xl bg-violet-500/10 p-2.5"
                  : "rounded-2xl p-2.5"
              }
            >
              <button
                type="button"
                disabled={!enabled}
                onClick={() => onSelectDate(date)}
                className={
                  selected
                    ? "block w-full text-left text-sm text-violet-300"
                    : isToday
                      ? "block w-full text-left text-sm text-neutral-200"
                      : "block w-full text-left text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
                }
              >
                {day}
              </button>
              {enabled && listedHabits.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {listedHabits.map((habit) => {
                    const active = lookup[`${habit.id}-${date}`] === true;
                    return (
                      <button
                        key={habit.id}
                        type="button"
                        aria-pressed={active}
                        aria-label={`${habit.name} on ${date}: ${
                          active ? "completed" : "not completed"
                        }${habit.is_archived ? ", archived" : ""}`}
                        onClick={() => {
                          onSelectDate(date);
                          if (!habit.is_archived) {
                            onToggle(habit.id, date, active ? "0" : "1");
                          }
                        }}
                        className="flex h-5 w-5 items-center justify-center"
                      >
                        <span
                          className={
                            active
                              ? "h-2.5 w-2.5 rounded-full bg-violet-400"
                              : "h-2.5 w-2.5 rounded-full bg-neutral-700"
                          }
                        />
                      </button>
                    );
                  })}
                </div>
              )}
              {enabled && listedHabits.length > 0 && (
                <span className="sr-only">
                  {completed} of {listedHabits.length} complete
                </span>
              )}
            </div>
          );
        })}
      </div>

      {listedHabits.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-x-4 gap-y-2">
          {listedHabits.map((habit) => (
            <li key={habit.id} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-violet-400" />
              {onSelectHabit ? (
                <button
                  type="button"
                  className="text-xs text-neutral-400 transition-colors duration-150 hover:text-neutral-200"
                  aria-label={`Open ${habit.name} history`}
                  onClick={() => onSelectHabit(habit.id)}
                >
                  {habit.name}
                </button>
              ) : (
                <span className="text-xs text-neutral-400">{habit.name}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default HabitGrid;

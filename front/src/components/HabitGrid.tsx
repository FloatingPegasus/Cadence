import { habitMarkClass } from "../habitMark";
import { todayAsLocalDate } from "../time";

interface HabitGridProps {
  habits: { id: number; name: string; is_archived: boolean }[];
  days: number[];
  month: string;
  lookup: Record<string, boolean>;
  selectedDate: string | null;
  onSelectDate: (dateStr: string) => void;
  onSelectHabit?: (habitId: number) => void;
}

const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function listedHabitsFor(
  habits: HabitGridProps["habits"],
): HabitGridProps["habits"] {
  const visible = habits.filter((habit) => !habit.is_archived);
  return visible.length > 0 ? visible : habits;
}

function HabitGrid({
  habits,
  days,
  month,
  lookup,
  selectedDate,
  onSelectDate,
  onSelectHabit,
}: HabitGridProps) {
  const [year, monthNumber] = month.split("-").map(Number);
  const leading = new Date(year, monthNumber - 1, 1).getDay();
  const lastDay = new Date(year, monthNumber, 0).getDate();
  const available = new Set(days);
  const today = todayAsLocalDate();
  const listedHabits = listedHabitsFor(habits);

  function dateStr(day: number) {
    return `${month}-${String(day).padStart(2, "0")}`;
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-y-3">
        {weekdays.map((day) => (
          <div
            key={day}
            className="pb-1 text-center text-[11px] text-neutral-500 sm:pb-2"
          >
            <span className="sm:hidden">{day.slice(0, 1)}</span>
            <span className="hidden sm:inline">{day}</span>
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
                  ? "rounded-xl bg-violet-500/10 p-1.5 sm:rounded-2xl sm:p-2.5"
                  : "rounded-xl p-1.5 sm:rounded-2xl sm:p-2.5"
              }
            >
              <button
                type="button"
                disabled={!enabled}
                onClick={() => onSelectDate(date)}
                aria-current={selected ? "date" : undefined}
                aria-label={
                  listedHabits.length > 0
                    ? `${date}, ${completed} of ${listedHabits.length} complete`
                    : date
                }
                className={
                  selected
                    ? "flex min-h-11 w-full flex-col items-start text-left text-sm text-violet-300"
                    : isToday
                      ? "flex min-h-11 w-full flex-col items-start text-left text-sm text-neutral-200"
                      : "flex min-h-11 w-full flex-col items-start text-left text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
                }
              >
                <span aria-hidden="true">{day}</span>
                {enabled && listedHabits.length > 0 && (
                  <span className="mt-2 flex flex-wrap gap-1">
                    {listedHabits.map((habit) => {
                      const active = lookup[`${habit.id}-${date}`] === true;
                      return (
                        <span
                          key={habit.id}
                          className={
                            active
                              ? `h-2.5 w-2.5 rounded-full ${habitMarkClass(habit.id)}`
                              : "h-2.5 w-2.5 rounded-full bg-neutral-700"
                          }
                        />
                      );
                    })}
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {listedHabits.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-x-4 gap-y-2">
          {listedHabits.map((habit) => (
            <li key={habit.id} className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${habitMarkClass(habit.id)}`}
              />
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

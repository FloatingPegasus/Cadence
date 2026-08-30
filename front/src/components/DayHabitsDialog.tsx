import { useEffect, useId, useRef } from "react";

import { habitMarkClass } from "../habitMark";

interface DayHabit {
  id: number;
  name: string;
  is_archived: boolean;
}

interface DayHabitsDialogProps {
  date: string;
  habits: DayHabit[];
  lookup: Record<string, boolean>;
  onToggle: (habitId: number, dateStr: string, newVal: string) => void;
  onOpenDay: () => void;
  onClose: () => void;
}

function listedHabitsFor(habits: DayHabit[]): DayHabit[] {
  const visible = habits.filter((habit) => !habit.is_archived);
  return visible.length > 0 ? visible : habits;
}

function formatDayHeading(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export default function DayHabitsDialog({
  date,
  habits,
  lookup,
  onToggle,
  onOpenDay,
  onClose,
}: DayHabitsDialogProps) {
  const headingId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  const listedHabits = listedHabitsFor(habits);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement;
    dialogRef.current?.focus();
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = originalOverflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-50/35 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        tabIndex={-1}
        className="cadence-surface w-full max-w-sm outline-none"
      >
        <h2
          id={headingId}
          className="cadence-title text-xl font-medium text-neutral-100"
        >
          {formatDayHeading(date)}
        </h2>

        {listedHabits.length > 0 ? (
          <div className="mt-6 space-y-1">
            {listedHabits.map((habit) => {
              const completed = lookup[`${habit.id}-${date}`] === true;
              return (
                <label
                  key={habit.id}
                  className="flex min-h-11 items-center justify-between gap-3 py-3 text-sm text-neutral-200"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${habitMarkClass(habit.id)}`}
                    />
                    <span className="truncate">{habit.name}</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={completed}
                    disabled={habit.is_archived}
                    onChange={() =>
                      onToggle(habit.id, date, completed ? "0" : "1")
                    }
                    aria-label={`Mark ${habit.name} complete for ${date}`}
                    className="h-6 w-6 accent-violet-500"
                  />
                </label>
              );
            })}
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap gap-2">
          <button type="button" onClick={onOpenDay} className="cadence-chip">
            Open day
          </button>
          <button type="button" onClick={onClose} className="cadence-chip">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

import type { KeyboardEvent } from "react";

export type DashboardView =
  | "today"
  | "hours"
  | "focus"
  | "calendar"
  | "continuity"
  | "settings";

interface DashboardNavProps {
  view: DashboardView;
  onChange: (view: DashboardView) => void;
}

const views: Array<{ id: DashboardView; label: string }> = [
  { id: "today", label: "Today" },
  { id: "hours", label: "Hours" },
  { id: "focus", label: "Focus" },
  { id: "calendar", label: "Calendar" },
  { id: "continuity", label: "History" },
  { id: "settings", label: "Settings" },
];

export default function DashboardNav({
  view,
  onChange,
}: DashboardNavProps) {
  function handleKey(
    event: KeyboardEvent<HTMLButtonElement>,
    current: DashboardView,
  ) {
    const index = views.findIndex((item) => item.id === current);
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % views.length;
    else if (event.key === "ArrowLeft") {
      next = (index - 1 + views.length) % views.length;
    } else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = views.length - 1;
    else return;
    event.preventDefault();
    const nextView = views[next].id;
    onChange(nextView);
    document.getElementById(`dashboard-nav-${nextView}`)?.focus();
  }

  return (
    <nav aria-label="Primary" className="cadence-rail mb-12">
      <div className="flex gap-7 overflow-x-auto pb-3">
        {views.map((item) => (
          <button
            key={item.id}
            id={`dashboard-nav-${item.id}`}
            type="button"
            aria-current={view === item.id ? "page" : undefined}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => handleKey(event, item.id)}
            className={
              view === item.id
                ? "border-b border-violet-400 pb-1 text-sm text-neutral-100"
                : "border-b border-transparent pb-1 text-sm text-neutral-500 transition-colors duration-200 hover:text-neutral-200"
            }
          >
            {item.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

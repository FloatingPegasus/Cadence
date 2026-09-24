import type { KeyboardEvent } from "react";

export type DashboardView =
  | "today"
  | "tasks"
  | "hours"
  | "focus"
  | "continuity"
  | "settings";

interface DashboardNavProps {
  view: DashboardView;
  onChange: (view: DashboardView) => void;
}

const views: Array<{ id: DashboardView; label: string }> = [
  { id: "today", label: "Today" },
  { id: "tasks", label: "Tasks" },
  { id: "hours", label: "Hours" },
  { id: "focus", label: "Focus" },
  { id: "continuity", label: "History" },
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
    <nav aria-label="Primary" className="cadence-rail mb-6 sm:mb-10">
      <div className="grid grid-cols-5 gap-x-1 pb-1 sm:flex sm:gap-7 sm:pb-3">
        {views.map((item) => (
          <button
            key={item.id}
            id={`dashboard-nav-${item.id}`}
            type="button"
            aria-current={view === item.id ? "page" : undefined}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => handleKey(event, item.id)}
            className="flex min-h-11 items-center justify-center px-1 text-sm"
          >
            <span
              className={
                view === item.id
                  ? "relative pb-px font-medium text-neutral-100"
                  : "pb-px text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
              }
            >
              {item.label}
              {view === item.id ? (
                <svg
                  className="cadence-tab-underline"
                  viewBox="0 0 60 6"
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <path
                    d="M2 4.2C14 2.4 30 3.6 44 2.8S56 3.6 58 3.2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              ) : null}
            </span>
          </button>
        ))}
      </div>
    </nav>
  );
}

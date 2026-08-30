import { useState, type KeyboardEvent } from "react";

import type { ContinuityContext } from "../api";
import ContextHub from "./ContextHub";
import ContinuitySearch from "./ContinuitySearch";
import MonthlyContinuity from "./MonthlyContinuity";
import WeeklyContinuity from "./WeeklyContinuity";
import ContinuityPatterns from "./ContinuityPatterns";

type ExplorerView = "contexts" | "search" | "week" | "month" | "patterns";

interface ContinuityExplorerProps {
  contexts: ContinuityContext[];
  anchorDate: string;
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
  refreshKey: number;
}

const views: Array<{ id: ExplorerView; label: string }> = [
  { id: "contexts", label: "Areas" },
  { id: "search", label: "Search" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "patterns", label: "Patterns" },
];

export default function ContinuityExplorer({
  contexts,
  anchorDate,
  selectedDate,
  onSelectDate,
  refreshKey,
}: ContinuityExplorerProps) {
  const [view, setView] = useState<ExplorerView>("week");

  function handleTabKey(
    event: KeyboardEvent<HTMLButtonElement>,
    currentView: ExplorerView,
  ) {
    const currentIndex = views.findIndex((item) => item.id === currentView);
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % views.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + views.length) % views.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = views.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    const nextView = views[nextIndex].id;
    setView(nextView);
    document.getElementById(`continuity-tab-${nextView}`)?.focus();
  }

  return (
    <section aria-label="History browser">
      <div className="flex flex-wrap items-baseline justify-between gap-6">
        <h1 className="cadence-title text-2xl font-medium text-neutral-100">
          History
        </h1>
        <div
          role="tablist"
          aria-label="History views"
          className="cadence-rail flex flex-wrap gap-x-3 gap-y-1 pb-2"
        >
          {views.map((item) => (
            <button
              key={item.id}
              id={`continuity-tab-${item.id}`}
              type="button"
              role="tab"
              aria-selected={view === item.id}
              aria-controls="continuity-explorer-panel"
              tabIndex={view === item.id ? 0 : -1}
              onClick={() => setView(item.id)}
              onKeyDown={(event) => handleTabKey(event, item.id)}
              className={
                view === item.id
                  ? "min-h-11 px-1 text-sm text-violet-300"
                  : "min-h-11 px-1 text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-300"
              }
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div
        id="continuity-explorer-panel"
        role="tabpanel"
        aria-labelledby={`continuity-tab-${view}`}
        className="cadence-surface mt-8 sm:mt-12"
      >
        {view === "contexts" && (
          <ContextHub
            contexts={contexts}
            onSelectDate={onSelectDate}
            refreshKey={refreshKey}
            embedded
          />
        )}
        {view === "search" && (
          <ContinuitySearch
            contexts={contexts}
            onSelectDate={onSelectDate}
            embedded
          />
        )}
        {view === "week" && (
          <WeeklyContinuity
            anchorDate={anchorDate}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            refreshKey={refreshKey}
            embedded
          />
        )}
        {view === "month" && (
          <MonthlyContinuity
            anchorDate={anchorDate}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            refreshKey={refreshKey}
            embedded
          />
        )}
        {view === "patterns" && (
          <ContinuityPatterns
            anchorDate={anchorDate}
            refreshKey={refreshKey}
          />
        )}
      </div>
    </section>
  );
}

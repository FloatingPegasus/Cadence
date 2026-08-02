import type { ContinuityContext } from "../api";
import CarryForwardCard from "./daily/CarryForwardCard";
import DailyCaptureCard from "./daily/DailyCaptureCard";
import DayClosureCard from "./daily/DayClosureCard";
import DailySummaryCard from "./daily/DailySummaryCard";
import QuickThreadCard from "./daily/QuickThreadCard";
import ReentryCard from "./daily/ReentryCard";

interface DailyPanelProps {
  date: string;
  contexts: ContinuityContext[];
  refreshKey: number;
  onSelectDate: (date: string) => void;
  onChanged: () => void;
}

export default function DailyPanel({
  date,
  contexts,
  refreshKey,
  onSelectDate,
  onChanged,
}: DailyPanelProps) {
  const [view, setView] = useState<"capture" | "threads" | "reflect">(
    "capture",
  );

  return (
    <div className="mt-6">
      <div aria-label="Daily sections" className="flex gap-5 border-b border-neutral-800">
        {(["capture", "threads", "reflect"] as const).map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={view === item}
            onClick={() => setView(item)}
            className={
              view === item
                ? "border-b border-violet-400 px-0.5 py-2 text-xs capitalize text-neutral-200"
                : "border-b border-transparent px-0.5 py-2 text-xs capitalize text-neutral-600 transition-colors duration-150 hover:text-neutral-300"
            }
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {view === "capture" && (
          <>
            <ReentryCard
              date={date}
              refreshKey={refreshKey}
              onSelectDate={onSelectDate}
            />
            <DailyCaptureCard
              date={date}
              contexts={contexts}
              onChanged={onChanged}
            />
          </>
        )}
        {view === "threads" && (
          <>
            <QuickThreadCard date={date} onChanged={onChanged} />
            <CarryForwardCard date={date} onChanged={onChanged} />
          </>
        )}
        {view === "reflect" && (
          <>
            <DailySummaryCard
              date={date}
              refreshKey={refreshKey}
              onChanged={onChanged}
            />
            <DayClosureCard
              date={date}
              refreshKey={refreshKey}
              onChanged={onChanged}
            />
          </>
        )}
      </div>
    </div>
  );
}
import { useState } from "react";

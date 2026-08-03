import { useState } from "react";

import {
  generateSummary,
  type ContinuityContext,
  type Habit,
} from "../api";
import { useAuth } from "../contexts/AuthContext";
import CarryForwardCard from "./daily/CarryForwardCard";
import DailyCaptureCard from "./daily/DailyCaptureCard";
import DailyHabitsCard from "./daily/DailyHabitsCard";
import DayClosureCard from "./daily/DayClosureCard";
import DailySummaryCard from "./daily/DailySummaryCard";
import QuickThreadCard from "./daily/QuickThreadCard";
import ReentryCard from "./daily/ReentryCard";

interface DailyPanelProps {
  date: string;
  habits: Habit[];
  contexts: ContinuityContext[];
  refreshKey: number;
  onSelectDate: (date: string) => void;
  onChanged: () => void;
  onHabitsChanged: () => void;
}

export default function DailyPanel({
  date,
  habits,
  contexts,
  refreshKey,
  onSelectDate,
  onChanged,
  onHabitsChanged,
}: DailyPanelProps) {
  const { user } = useAuth();
  const [view, setView] = useState<"log" | "followups" | "summary">("log");
  const [summaryStatus, setSummaryStatus] = useState<string | null>(null);

  function sourceChanged(hasSource = true) {
    onChanged();
    if (!hasSource || !user?.ai_processing_consent) return;

    setSummaryStatus("Updating your summary…");
    void generateSummary(date)
      .then(() => setSummaryStatus("Summary updated"))
      .catch((caught) => {
        const message = caught instanceof Error ? caught.message : "";
        setSummaryStatus(
          message.toLowerCase().includes("edited summary")
            ? "Your edited summary was kept"
            : "Summary could not be updated automatically",
        );
      });
  }

  const sections = [
    { id: "log" as const, label: "Today" },
    { id: "followups" as const, label: "Follow-ups" },
    { id: "summary" as const, label: "Summary" },
  ];

  return (
    <div className="mt-6">
      <div
        aria-label="Daily sections"
        className="flex gap-5 border-b border-neutral-800"
      >
        {sections.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={view === item.id}
            onClick={() => setView(item.id)}
            className={
              view === item.id
                ? "border-b border-violet-400 px-0.5 py-2 text-xs capitalize text-neutral-200"
                : "border-b border-transparent px-0.5 py-2 text-xs capitalize text-neutral-600 transition-colors duration-150 hover:text-neutral-300"
            }
          >
            {item.label}
          </button>
        ))}
      </div>
      {summaryStatus && (
        <p role="status" className="mt-3 text-xs text-neutral-500">
          {summaryStatus}
        </p>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {view === "log" && (
          <>
            <ReentryCard
              date={date}
              refreshKey={refreshKey}
              onSelectDate={onSelectDate}
            />
            <DailyHabitsCard
              date={date}
              habits={habits}
              refreshKey={refreshKey}
              onHabitsChanged={onHabitsChanged}
              onSourceChanged={() => sourceChanged(true)}
            />
            <DailyCaptureCard
              date={date}
              contexts={contexts}
              onChanged={sourceChanged}
            />
            <QuickThreadCard
              date={date}
              onChanged={() => sourceChanged(true)}
            />
          </>
        )}
        {view === "followups" && (
          <>
            <CarryForwardCard date={date} onChanged={onChanged} />
          </>
        )}
        {view === "summary" && (
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

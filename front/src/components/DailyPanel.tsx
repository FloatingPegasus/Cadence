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

  return (
    <div className="mt-6 cadence-enter">
      {summaryStatus && (
        <p role="status" className="mb-3 text-xs text-neutral-500">
          {summaryStatus}
        </p>
      )}
      <div className="grid gap-6">
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
        <CarryForwardCard date={date} onChanged={onChanged} />
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
      </div>
    </div>
  );
}

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

  function sourceChanged(hasSource = true) {
    onChanged();
    if (!hasSource || !user?.ai_processing_consent) return;
    void generateSummary(date).catch(() => {});
  }

  return (
    <div className="mt-6 sm:mt-12">
      <div className="grid gap-5">
        <ReentryCard
          date={date}
          refreshKey={refreshKey}
          onSelectDate={onSelectDate}
        />
        <div className="cadence-surface">
          <DailyHabitsCard
            date={date}
            habits={habits}
            refreshKey={refreshKey}
            onHabitsChanged={onHabitsChanged}
            onSourceChanged={() => sourceChanged(true)}
          />
        </div>
        <div className="cadence-surface">
          <DailyCaptureCard
            date={date}
            contexts={contexts}
            onChanged={sourceChanged}
          />
        </div>
        <div className="cadence-surface space-y-1">
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
    </div>
  );
}

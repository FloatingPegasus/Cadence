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
  onOpenHour?: (date: string) => void;
  onOpenTask?: () => void;
  onChanged: () => void;
  onHabitsChanged: () => void;
}

export default function DailyPanel({
  date,
  habits,
  contexts,
  refreshKey,
  onSelectDate,
  onOpenHour,
  onOpenTask,
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
    <div className="mt-5 sm:mt-8">
      <div className="grid gap-4">
        <ReentryCard
          date={date}
          refreshKey={refreshKey}
          onSelectDate={onSelectDate}
          onOpenHour={onOpenHour}
          onOpenTask={onOpenTask}
        />
        <div className="cadence-surface cadence-note">
          <DailyHabitsCard
            date={date}
            habits={habits}
            refreshKey={refreshKey}
            onHabitsChanged={onHabitsChanged}
            onSourceChanged={() => sourceChanged(true)}
          />
        </div>
        <div className="cadence-surface cadence-surface-quiet">
          <DailyCaptureCard
            date={date}
            contexts={contexts}
            onChanged={sourceChanged}
          />
        </div>
        <div className="cadence-surface cadence-surface-quiet space-y-1">
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

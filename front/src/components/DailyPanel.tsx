import { useEffect, useState } from "react";

import { generateSummary, type ContinuityContext } from "../api";
import { useAuth } from "../contexts/AuthContext";
import { todayAsLocalDate } from "../time";
import CarryForwardCard from "./daily/CarryForwardCard";
import CloseDayCard from "./daily/CloseDayCard";
import DailySummaryCard from "./daily/DailySummaryCard";
import LogNote from "./daily/LogNote";
import ReentryCard from "./daily/ReentryCard";
import TodayList from "./daily/TodayList";

const EVENING_HOUR = 18;

interface DailyPanelProps {
  date: string;
  contexts: ContinuityContext[];
  refreshKey: number;
  onSelectDate: (date: string) => void;
  onOpenHour?: (date: string) => void;
  onOpenTask?: () => void;
  onStartFocus: () => void;
  onChanged: () => void;
  onHabitsChanged: () => void;
  onTasksChanged: () => void;
}

function useCurrentHour() {
  const [hour, setHour] = useState(() => new Date().getHours());
  useEffect(() => {
    const timer = window.setInterval(
      () => setHour(new Date().getHours()),
      60_000,
    );
    return () => window.clearInterval(timer);
  }, []);
  return hour;
}

export default function DailyPanel({
  date,
  contexts,
  refreshKey,
  onSelectDate,
  onOpenHour,
  onOpenTask,
  onStartFocus,
  onChanged,
  onHabitsChanged,
  onTasksChanged,
}: DailyPanelProps) {
  const { user, aiEnabled } = useAuth();
  const hour = useCurrentHour();
  const isToday = date === todayAsLocalDate();
  const [chosen, setChosen] = useState<"log" | "close" | null>(null);

  useEffect(() => {
    setChosen(null);
  }, [date]);

  const evening = hour >= EVENING_HOUR || hour < (user?.day_ends_at ?? 0);
  const mode = !isToday ? "close" : (chosen ?? (evening ? "close" : "log"));

  function sourceChanged(hasSource = true) {
    onChanged();
    if (!hasSource || !aiEnabled || !user?.ai_processing_consent) return;
    void generateSummary(date).catch(() => {});
  }

  return (
    <div className="mt-5 grid gap-4 sm:mt-8">
      <ReentryCard
        date={date}
        refreshKey={refreshKey}
        onSelectDate={onSelectDate}
        onOpenHour={onOpenHour}
        onOpenTask={onOpenTask}
      />
      <div>
        <div className="cadence-surface cadence-note">
          {mode === "log" ? (
            <LogNote
              date={date}
              hour={hour}
              refreshKey={refreshKey}
              onStartFocus={onStartFocus}
              onChanged={onChanged}
            />
          ) : (
            <CloseDayCard
              date={date}
              contexts={contexts}
              onChanged={sourceChanged}
            >
              {aiEnabled ? (
                <DailySummaryCard
                  date={date}
                  refreshKey={refreshKey}
                  onChanged={onChanged}
                />
              ) : null}
              <CarryForwardCard date={date} onChanged={onChanged} />
            </CloseDayCard>
          )}
        </div>
        {isToday ? (
          <button
            type="button"
            onClick={() => setChosen(mode === "log" ? "close" : "log")}
            className="mt-1 min-h-11 px-0.5 text-sm text-violet-300 hover:text-violet-200"
          >
            {mode === "log" ? "Close the day" : "Log something"}
          </button>
        ) : null}
      </div>
      <div className="mt-2">
        <TodayList
          date={date}
          refreshKey={refreshKey}
          onHabitsChanged={onHabitsChanged}
          onChanged={onTasksChanged}
        />
      </div>
    </div>
  );
}

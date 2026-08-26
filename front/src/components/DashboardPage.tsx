import { useEffect, useState } from "react";

import {
  fetchHabits,
  fetchContexts,
  fetchMonthData,
  toggleHabit,
  type ContinuityContext,
  type Habit,
  type MonthData,
} from "../api";
import { useAuth } from "../contexts/AuthContext";
import DailyPanel from "./DailyPanel";
import DisciplineContinuity from "./DisciplineContinuity";
import ContinuityExplorer from "./ContinuityExplorer";
import DashboardNav, { type DashboardView } from "./DashboardNav";
import FocusPage from "./FocusPage";
import HabitGrid from "./HabitGrid";
import Header from "./Header";
import HoursPage from "./HoursPage";
import MonthNav from "./MonthNav";
import RecentDays from "./RecentDays";
import SettingsPanel from "./SettingsPanel";
import { todayAsLocalDate } from "../time";

export default function DashboardPage() {
  const { user } = useAuth();
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [data, setData] = useState<MonthData | null>(null);
  const [habits, setHabits] = useState<Habit[]>([]);
  const [contexts, setContexts] = useState<ContinuityContext[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(
    todayAsLocalDate,
  );
  const [selectedHabitId, setSelectedHabitId] = useState<number | null>(null);
  const [view, setView] = useState<DashboardView>("today");
  const [continuityVersion, setContinuityVersion] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [habitVersion, setHabitVersion] = useState(0);
  const [contextVersion, setContextVersion] = useState(0);

  useEffect(() => {
    if (!user) {
      setHabits([]);
      setData(null);
      setSelectedDate(null);
      setSelectedHabitId(null);
      return;
    }
    fetchHabits()
      .then(setHabits)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load habits",
        );
      });
  }, [user, habitVersion]);

  useEffect(() => {
    if (!user) {
      setContexts([]);
      return;
    }
    fetchContexts()
      .then(setContexts)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load areas",
        );
      });
  }, [user, contextVersion]);

  useEffect(() => {
    if (!user || view !== "calendar") return;
    fetchMonthData(month)
      .then(setData)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load the month",
        );
      });
  }, [user, month, habitVersion, view]);

  function handleToggle(habitId: number, dateStr: string, newVal: string) {
    const key = `${habitId}-${dateStr}`;
    setActionError(null);
    setData((previous) => {
      if (!previous) return previous;
      const lookup = { ...previous.lookup };
      if (newVal === "1") {
        lookup[key] = true;
      } else {
        delete lookup[key];
      }
      return { ...previous, lookup };
    });

    toggleHabit(habitId, dateStr, newVal)
      .then(() => {
        setContinuityVersion((version) => version + 1);
      })
      .catch((error) => {
        setData((previous) => {
          if (!previous) return previous;
          const lookup = { ...previous.lookup };
          if (newVal === "1") {
            delete lookup[key];
          } else {
            lookup[key] = true;
          }
          return { ...previous, lookup };
        });
        setActionError(
          error instanceof Error ? error.message : "Could not update habit",
        );
      });
  }

  function openDay(date: string) {
    setSelectedDate(date);
    setView("today");
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Header />
      <DashboardNav view={view} onChange={setView} />
      {actionError && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {actionError}
        </div>
      )}
      {view === "today" && selectedDate && (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h1 className="text-base font-medium text-neutral-100">
              Today
            </h1>
            <label className="text-xs text-neutral-500">
              Day
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                className="ml-2 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-300 outline-none transition-colors duration-200 focus:border-neutral-600"
              />
            </label>
          </div>
          <DailyPanel
            date={selectedDate}
            habits={habits}
            contexts={contexts}
            refreshKey={continuityVersion}
            onSelectDate={setSelectedDate}
            onChanged={() =>
              setContinuityVersion((version) => version + 1)
            }
            onHabitsChanged={() =>
              setHabitVersion((version) => version + 1)
            }
          />
          <RecentDays
            selectedDate={selectedDate}
            onSelect={setSelectedDate}
            refreshKey={continuityVersion}
          />
        </>
      )}
      {view === "hours" && selectedDate && (
        <HoursPage
          date={selectedDate}
          onSelectDate={setSelectedDate}
          onChanged={() =>
            setContinuityVersion((version) => version + 1)
          }
        />
      )}
      {view === "focus" && <FocusPage />}
      {view === "calendar" && (
        <>
          <h1 className="mb-5 text-base font-medium text-neutral-100">
            Calendar
          </h1>
          <MonthNav month={month} onChange={setMonth} />
          {data && data.habits.length > 0 ? (
            <HabitGrid
              habits={data.habits}
              days={data.days}
              month={data.month}
              lookup={data.lookup}
              onToggle={handleToggle}
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
              onSelectHabit={setSelectedHabitId}
            />
          ) : (
            <p className="text-sm text-neutral-500">
              Habits you add on Today show up here as a month grid.
            </p>
          )}
          {selectedDate && (
            <button
              type="button"
              onClick={() => openDay(selectedDate)}
              className="mt-3 text-xs text-neutral-500 transition-colors duration-150 hover:text-neutral-200"
            >
              Open selected day
            </button>
          )}
          {selectedHabitId !== null && data && (
            <DisciplineContinuity
              disciplineId={selectedHabitId}
              month={data.month}
              selectedDate={selectedDate}
              onSelectDate={openDay}
              refreshKey={continuityVersion}
              onClose={() => setSelectedHabitId(null)}
            />
          )}
        </>
      )}
      {view === "continuity" && (
        <>
          <h1 className="text-base font-medium text-neutral-100">
            History
          </h1>
          <ContinuityExplorer
            contexts={contexts}
            anchorDate={selectedDate ?? todayAsLocalDate()}
            selectedDate={selectedDate}
            onSelectDate={openDay}
            refreshKey={continuityVersion}
          />
        </>
      )}
      {view === "settings" && (
        <SettingsPanel
          habits={habits}
          contexts={contexts}
          isDeveloper={user?.is_developer ?? false}
          onHabitsChanged={() =>
            setHabitVersion((version) => version + 1)
          }
          onContextsChanged={() =>
            setContextVersion((version) => version + 1)
          }
        />
      )}
    </div>
  );
}

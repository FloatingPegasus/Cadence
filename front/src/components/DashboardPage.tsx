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
import HabitGrid from "./HabitGrid";
import Header from "./Header";
import MonthNav from "./MonthNav";
import RecentDays from "./RecentDays";
import SettingsPanel from "./SettingsPanel";

function todayAsLocalDate() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

export default function DashboardPage() {
  const { token, user } = useAuth();
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
    if (!token) {
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
          caught instanceof Error ? caught.message : "Could not load disciplines",
        );
      });
  }, [token, habitVersion]);

  useEffect(() => {
    if (!token) {
      setContexts([]);
      return;
    }
    fetchContexts()
      .then(setContexts)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load contexts",
        );
      });
  }, [token, contextVersion]);

  useEffect(() => {
    if (!token || view !== "calendar") return;
    fetchMonthData(month)
      .then(setData)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load the month",
        );
      });
  }, [token, month, habitVersion, view]);

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
            <div>
              <h1 className="text-base font-medium text-neutral-100">
                Today
              </h1>
              <p className="mt-1 text-sm text-neutral-500">
                Keep a simple record of what happened.
              </p>
            </div>
            <label className="text-xs text-neutral-500">
              Day
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                className="ml-2 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-300 outline-none focus:border-neutral-600"
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
      {view === "calendar" && (
        <>
          <div className="mb-5">
            <h1 className="text-base font-medium text-neutral-100">
              Calendar
            </h1>
            <p className="mt-1 text-sm text-neutral-500">
              A simple record of practice over time.
            </p>
          </div>
          <MonthNav month={month} onChange={setMonth} />
          {data && (
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
          <div>
            <h1 className="text-base font-medium text-neutral-100">
              History
            </h1>
            <p className="mt-1 text-sm text-neutral-500">
              Look back at the days and notes you have recorded.
            </p>
          </div>
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

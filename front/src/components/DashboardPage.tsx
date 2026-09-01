import { useEffect, useState } from "react";

import {
  fetchHabits,
  fetchContexts,
  fetchMonthData,
  fetchTasks,
  createTask,
  updateTask,
  toggleHabit,
  type ContinuityContext,
  type Habit,
  type MonthData,
  type TaskItem,
} from "../api";
import { useAuth } from "../contexts/AuthContext";
import DailyPanel from "./DailyPanel";
import DisciplineContinuity from "./DisciplineContinuity";
import ContinuityExplorer from "./ContinuityExplorer";
import DashboardNav, { type DashboardView } from "./DashboardNav";
import FocusPage from "./FocusPage";
import DayHabitsDialog from "./DayHabitsDialog";
import HabitGrid from "./HabitGrid";
import Header from "./Header";
import HoursPage from "./HoursPage";
import MonthNav from "./MonthNav";
import RecentDays from "./RecentDays";
import SettingsPanel from "./SettingsPanel";
import TasksPage from "./TasksPage";
import ViewPane from "./ViewPane";
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
  const [opened, setOpened] = useState<Set<DashboardView>>(
    () => new Set(["today", "tasks"]),
  );
  const [continuityVersion, setContinuityVersion] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [habitVersion, setHabitVersion] = useState(0);
  const [taskVersion, setTaskVersion] = useState(0);
  const [contextVersion, setContextVersion] = useState(0);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [dayDialogOpen, setDayDialogOpen] = useState(false);

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
    if (!user || !opened.has("calendar")) return;
    fetchMonthData(month)
      .then(setData)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load the month",
        );
      });
  }, [user, month, habitVersion, opened]);

  useEffect(() => {
    if (!user || !(opened.has("tasks") || opened.has("calendar"))) return;
    fetchTasks()
      .then(setTasks)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load tasks",
        );
      });
  }, [user, taskVersion, opened]);

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

  function handleToggleTask(task: TaskItem) {
    const next = !task.is_completed;
    setActionError(null);
    setTasks((current) =>
      current.map((item) =>
        item.id === task.id ? { ...item, is_completed: next } : item,
      ),
    );
    updateTask(task.id, { is_completed: next })
      .then((saved) => {
        setTasks((current) =>
          current.map((item) => (item.id === saved.id ? saved : item)),
        );
        setTaskVersion((version) => version + 1);
      })
      .catch((error) => {
        setTasks((current) =>
          current.map((item) => (item.id === task.id ? task : item)),
        );
        setActionError(
          error instanceof Error ? error.message : "Could not update the task",
        );
      });
  }

  async function handleAddTask(title: string) {
    if (!selectedDate) return;
    setActionError(null);
    try {
      const created = await createTask(title, selectedDate);
      setTasks((current) => [...current, created]);
      setTaskVersion((version) => version + 1);
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Could not add the task",
      );
      throw error;
    }
  }

  function openDateDialog(date: string) {
    setSelectedDate(date);
    setDayDialogOpen(true);
  }

  function openView(next: DashboardView) {
    setView(next);
    setOpened((current) => {
      if (current.has(next)) return current;
      const nextOpened = new Set(current);
      nextOpened.add(next);
      return nextOpened;
    });
    if (next !== "calendar") setDayDialogOpen(false);
  }

  function openDay(date: string) {
    setDayDialogOpen(false);
    setSelectedDate(date);
    openView("today");
  }

  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:px-8 sm:py-16">
      <Header />
      <DashboardNav view={view} onChange={openView} />
      {actionError && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {actionError}
        </div>
      )}
      {opened.has("today") && selectedDate && (
        <ViewPane active={view === "today"}>
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h1 className="cadence-title text-2xl font-medium text-neutral-100">
              Today
            </h1>
            <label className="text-xs text-neutral-500">
              Day
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                className="ml-2 min-h-11 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-2 text-base text-neutral-300 outline-none transition-colors duration-200 focus:border-neutral-600 sm:min-h-0 sm:py-1.5 sm:text-xs"
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
        </ViewPane>
      )}
      {opened.has("tasks") && (
        <ViewPane active={view === "tasks"}>
          <TasksPage
            refreshKey={taskVersion}
            onChanged={() => setTaskVersion((version) => version + 1)}
          />
        </ViewPane>
      )}
      {opened.has("hours") && selectedDate && (
        <ViewPane active={view === "hours"}>
          <HoursPage
            date={selectedDate}
            onSelectDate={setSelectedDate}
            onChanged={() =>
              setContinuityVersion((version) => version + 1)
            }
          />
        </ViewPane>
      )}
      {opened.has("focus") && (
        <ViewPane active={view === "focus"}>
          <FocusPage />
        </ViewPane>
      )}
      {opened.has("calendar") && (
        <ViewPane active={view === "calendar"}>
          <MonthNav month={month} onChange={setMonth} />
          {data ? (
            <div className="cadence-surface">
              <HabitGrid
                habits={data.habits}
                days={data.days}
                month={data.month}
                lookup={data.lookup}
                selectedDate={selectedDate}
                onSelectDate={openDateDialog}
                onSelectHabit={setSelectedHabitId}
              />
            </div>
          ) : null}
          {dayDialogOpen && selectedDate && data && (
            <DayHabitsDialog
              date={selectedDate}
              habits={data.habits}
              lookup={data.lookup}
              tasks={tasks.filter((task) => task.due_date === selectedDate)}
              onToggle={handleToggle}
              onToggleTask={handleToggleTask}
              onAddTask={handleAddTask}
              onOpenDay={() => openDay(selectedDate)}
              onClose={() => setDayDialogOpen(false)}
            />
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
        </ViewPane>
      )}
      {opened.has("continuity") && (
        <ViewPane active={view === "continuity"}>
          <ContinuityExplorer
            contexts={contexts}
            anchorDate={selectedDate ?? todayAsLocalDate()}
            selectedDate={selectedDate}
            onSelectDate={openDay}
            refreshKey={continuityVersion}
          />
        </ViewPane>
      )}
      {opened.has("settings") && (
        <ViewPane active={view === "settings"}>
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
        </ViewPane>
      )}
    </div>
  );
}

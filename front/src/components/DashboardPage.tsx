import { useEffect, useState } from "react";

import {
  beginDay,
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
import SettingsPanel from "./SettingsPanel";
import TasksPage from "./TasksPage";
import ViewPane from "./ViewPane";
import { todayAsLocalDate } from "../time";

function longDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

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
  const [focusStart, setFocusStart] = useState(0);
  const today = todayAsLocalDate();

  useEffect(() => {
    if (!user) return;
    beginDay(today)
      .then(({ closed }) => {
        if (closed.length) setContinuityVersion((version) => version + 1);
      })
      .catch(() => {});
  }, [user?.id, today]);

  useEffect(() => {
    if (!user) {
      setHabits([]);
      setData(null);
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
  }, [user?.id, habitVersion]);

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
  }, [user?.id, contextVersion]);

  useEffect(() => {
    if (!user || !opened.has("continuity")) return;
    fetchMonthData(month)
      .then(setData)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load the month",
        );
      });
  }, [user?.id, month, habitVersion, opened]);

  useEffect(() => {
    if (!user || !(opened.has("tasks") || opened.has("continuity"))) return;
    fetchTasks()
      .then(setTasks)
      .catch((caught) => {
        setActionError(
          caught instanceof Error ? caught.message : "Could not load tasks",
        );
      });
  }, [user?.id, taskVersion, opened]);

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

  function refreshTasks() {
    setTaskVersion((version) => version + 1);
    setContinuityVersion((version) => version + 1);
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
    if (next !== "continuity") setDayDialogOpen(false);
  }

  function openDay(date: string) {
    setDayDialogOpen(false);
    setSelectedDate(date);
    openView("today");
  }

  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:px-8 sm:py-16">
      <Header
        settingsOpen={view === "settings"}
        onOpenSettings={() => openView("settings")}
      />
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
              {longDate(selectedDate)}
            </h1>
            {selectedDate !== today ? (
              <button
                type="button"
                onClick={() => setSelectedDate(today)}
                className="cadence-chip sm:text-xs"
              >
                Back to today
              </button>
            ) : null}
          </div>
          <DailyPanel
            date={selectedDate}
            contexts={contexts}
            refreshKey={continuityVersion}
            onSelectDate={setSelectedDate}
            onOpenHour={(date) => {
              setSelectedDate(date);
              openView("hours");
            }}
            onOpenTask={() => openView("tasks")}
            onStartFocus={() => {
              setFocusStart((count) => count + 1);
              openView("focus");
            }}
            onChanged={() =>
              setContinuityVersion((version) => version + 1)
            }
            onHabitsChanged={() =>
              setHabitVersion((version) => version + 1)
            }
            onTasksChanged={refreshTasks}
          />
        </ViewPane>
      )}
      {opened.has("tasks") && (
        <ViewPane active={view === "tasks"}>
          <TasksPage refreshKey={taskVersion} onChanged={refreshTasks} />
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
          <FocusPage startSignal={focusStart} />
        </ViewPane>
      )}
      {opened.has("continuity") && (
        <ViewPane active={view === "continuity"}>
          {user ? (
            <ContinuityExplorer
              contexts={contexts}
              anchorDate={selectedDate ?? today}
              selectedDate={selectedDate}
              onSelectDate={openDay}
              refreshKey={continuityVersion}
              calendar={
                <>
                  <MonthNav month={month} onChange={setMonth} />
                  {data ? (
                    <HabitGrid
                      habits={data.habits}
                      days={data.days}
                      month={data.month}
                      lookup={data.lookup}
                      selectedDate={selectedDate}
                      onSelectDate={openDateDialog}
                      onSelectHabit={setSelectedHabitId}
                    />
                  ) : null}
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
              }
            />
          ) : (
            <div>
              <h1 className="cadence-title text-2xl font-medium text-neutral-100">
                History
              </h1>
              <p className="mt-8 text-sm text-neutral-500">Nothing here yet.</p>
            </div>
          )}
          {dayDialogOpen && selectedDate && data && (
            <DayHabitsDialog
              date={selectedDate}
              habits={data.habits}
              lookup={data.lookup}
              tasks={tasks.filter(
                (task) =>
                  task.due_date === selectedDate && !task.is_abandoned,
              )}
              onToggle={handleToggle}
              onToggleTask={handleToggleTask}
              onAddTask={handleAddTask}
              onOpenDay={() => openDay(selectedDate)}
              onClose={() => setDayDialogOpen(false)}
            />
          )}
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

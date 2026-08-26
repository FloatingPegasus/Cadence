import type { GoalKind } from "./api";

export const GOAL_KIND_LABELS: Record<GoalKind, string> = {
  ultimate: "Ultimate",
  secondary: "Secondary",
  long_term: "Long term",
  short_term: "Short term",
};

export function todayAsLocalDate() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

export function formatHourLabel(hour: number) {
  const suffix = hour < 12 ? "AM" : "PM";
  const twelve = hour % 12 === 0 ? 12 : hour % 12;
  return `${twelve} ${suffix}`;
}

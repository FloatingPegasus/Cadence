export const HABIT_MARK_COUNT = 6;

export function habitMarkClass(id: number): string {
  const index = (((id - 1) % HABIT_MARK_COUNT) + HABIT_MARK_COUNT) % HABIT_MARK_COUNT;
  return `habit-mark-${index + 1}`;
}

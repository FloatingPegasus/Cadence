from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..continuity import service as continuity_service
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.task import Task
from ...persistence.models.user_goal import UserGoal
from ...persistence.models.weekly_reflection import WeeklyReflection

LAYER_CAPS = {
    "Goals": 800,
    "Habits": 800,
    "Tasks": 1_200,
    "Recent days": 4_000,
    "Today": 4_000,
}

GOAL_LABELS = {
    "long_term": "Long term",
    "short_term": "Short term",
    "ultimate": "Long term",
    "secondary": "Short term",
}

CHECKIN_LABELS = (
    ("energy_level", "Energy"),
    ("focus_quality", "Focus"),
    ("sleep_quality", "Sleep"),
    ("recovery_quality", "Recovery"),
    ("reentry_success", "Restarting"),
)


def _cap(text: str, limit: int, *, keep_end: bool = False) -> str:
    if len(text) <= limit:
        return text
    if keep_end:
        return "…" + text[-(limit - 1) :].lstrip()
    return text[: limit - 1].rstrip() + "…"


def _compact(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def _short_date(value: date) -> str:
    return f"{value:%a %b} {value.day}"


def _hour_label(hour: int) -> str:
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"


async def _goals(db: AsyncSession, user_id: int) -> str:
    goals = await db.scalars(
        select(UserGoal)
        .where(UserGoal.user_id == user_id)
        .order_by(UserGoal.sort_order, UserGoal.id)
    )
    return "\n".join(
        f"- {GOAL_LABELS.get(goal.kind, goal.kind)}: {goal.title}" for goal in goals
    )


async def _habits(db: AsyncSession, user_id: int, target_date: date) -> str:
    done = set(
        await db.scalars(
            select(HabitLog.habit_id)
            .join(Day, Day.id == HabitLog.day_id)
            .where(Day.user_id == user_id, Day.date == target_date)
        )
    )
    habits = await db.scalars(
        select(Habit)
        .where(Habit.user_id == user_id, Habit.is_archived.is_(False))
        .order_by(Habit.id)
    )
    return "\n".join(
        f"- {habit.name}: {'done' if habit.id in done else 'not yet'}"
        for habit in habits
    )


async def _tasks(db: AsyncSession, user_id: int, target_date: date) -> str:
    tasks = await db.scalars(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.is_completed.is_(False),
            Task.is_abandoned.is_(False),
            Task.due_date.is_not(None),
            Task.due_date <= target_date + timedelta(days=7),
        )
        .order_by(Task.due_date, Task.id)
        .limit(20)
    )
    lines = []
    for task in tasks:
        if task.due_date < target_date:
            when = f"overdue since {_short_date(task.due_date)}"
        elif task.due_date == target_date:
            when = "due today"
        else:
            when = f"due {_short_date(task.due_date)}"
        lines.append(f"- {task.title} ({when})")
    return "\n".join(lines)


async def _memory(
    db: AsyncSession, user_id: int, target_date: date, log_text: str
) -> str:
    week_start = target_date - timedelta(days=7)
    summaries = await db.execute(
        select(Day.date, SummaryArtifact.content)
        .join(SummaryArtifact, SummaryArtifact.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            SummaryArtifact.kind == "daily",
            Day.date >= week_start,
            Day.date < target_date,
        )
        .order_by(Day.date.desc())
    )
    lines = [
        f"- {_short_date(day)}: {_compact(content, 600)}"
        for day, content in summaries.all()
        if content.strip()
    ]
    reflection = await db.scalar(
        select(WeeklyReflection)
        .where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start <= target_date,
        )
        .order_by(WeeklyReflection.week_start.desc())
        .limit(1)
    )
    if reflection is not None and reflection.content.strip():
        lines.append(
            f"- Week of {_short_date(reflection.week_start)}: "
            f"{_compact(reflection.content, 1_000)}"
        )
    older = await continuity_service.similar_days(
        db, user_id, log_text, week_start - timedelta(days=1), 3
    )
    lines.extend(
        f"- Earlier, {_short_date(date.fromisoformat(item['date']))}: "
        f"{item['excerpt']}"
        for item in older
    )
    return "\n".join(lines)


async def _today(
    db: AsyncSession, user_id: int, target_date: date, exclude_id: int | None
) -> str:
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == target_date)
    )
    if day is None:
        return ""
    lines = []
    checkin = await db.scalar(
        select(DailyCheckin).where(DailyCheckin.day_id == day.id)
    )
    if checkin is not None:
        scores = [
            f"{label} {getattr(checkin, field)}/5"
            for field, label in CHECKIN_LABELS
            if getattr(checkin, field) is not None
        ]
        if scores:
            lines.append("Check-in: " + ", ".join(scores))
    if (day.daily_note or "").strip():
        lines.append(f"Day note: {_compact(day.daily_note, 600)}")
    entries = list(
        await db.scalars(
            select(ConversationEntry)
            .where(
                ConversationEntry.day_id == day.id,
                ConversationEntry.id != (exclude_id or 0),
            )
            .order_by(ConversationEntry.created_at.desc(), ConversationEntry.id.desc())
            .limit(20)
        )
    )
    for entry in reversed(entries):
        speaker = "Cadence" if entry.role == "assistant" else "They"
        when = f" at {_hour_label(entry.hour)}" if entry.hour is not None else ""
        lines.append(f"{speaker}{when}: {_compact(entry.content, 500)}")
    return "\n".join(lines)


async def build_context(
    db: AsyncSession,
    user_id: int,
    target_date: date,
    log_text: str,
    exclude_id: int | None = None,
) -> str:
    layers = [
        ("Goals", await _goals(db, user_id)),
        ("Habits", await _habits(db, user_id, target_date)),
        ("Tasks", await _tasks(db, user_id, target_date)),
        ("Recent days", await _memory(db, user_id, target_date, log_text)),
        ("Today", await _today(db, user_id, target_date, exclude_id)),
    ]
    return "\n\n".join(
        f"{title}:\n{_cap(body, LAYER_CAPS[title], keep_end=title == 'Today')}"
        for title, body in layers
        if body
    )

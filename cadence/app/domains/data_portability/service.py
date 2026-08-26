from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.user import User
from ...persistence.models.weekly_reflection import WeeklyReflection
from ...persistence.models.hour_log import HourLog
from ...persistence.models.user_goal import UserGoal

EXPORT_FORMAT = "cadence-export"
EXPORT_SCHEMA_VERSION = 2


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _record(model: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _serialize(getattr(model, field)) for field in fields}


async def export_user_data(
    db: AsyncSession,
    user: User,
) -> dict[str, Any]:
    habits = list(
        (
            await db.scalars(
                select(Habit)
                .where(Habit.user_id == user.id)
                .order_by(Habit.id)
            )
        ).all()
    )
    contexts = list(
        (
            await db.scalars(
                select(ContinuityContext)
                .where(ContinuityContext.user_id == user.id)
                .order_by(ContinuityContext.id)
            )
        ).all()
    )
    days = list(
        (
            await db.scalars(
                select(Day)
                .where(Day.user_id == user.id)
                .order_by(Day.date, Day.id)
            )
        ).all()
    )
    weekly_reflections = list(
        (
            await db.scalars(
                select(WeeklyReflection)
                .where(WeeklyReflection.user_id == user.id)
                .order_by(WeeklyReflection.week_start, WeeklyReflection.id)
            )
        ).all()
    )
    goals = list(
        (
            await db.scalars(
                select(UserGoal)
                .where(UserGoal.user_id == user.id)
                .order_by(UserGoal.sort_order, UserGoal.id)
            )
        ).all()
    )

    day_ids = [day.id for day in days]
    habit_ids = [habit.id for habit in habits]
    context_ids = [context.id for context in contexts]

    habit_logs: list[HabitLog] = []
    checkins: list[DailyCheckin] = []
    conversations: list[ConversationEntry] = []
    summaries: list[SummaryArtifact] = []
    carry_forward_items: list[CarryForwardItem] = []
    day_contexts: list[DayContext] = []
    hour_logs: list[HourLog] = []
    if day_ids:
        checkins = list(
            (
                await db.scalars(
                    select(DailyCheckin)
                    .where(DailyCheckin.day_id.in_(day_ids))
                    .order_by(DailyCheckin.day_id)
                )
            ).all()
        )
        conversations = list(
            (
                await db.scalars(
                    select(ConversationEntry)
                    .where(ConversationEntry.day_id.in_(day_ids))
                    .order_by(
                        ConversationEntry.day_id,
                        ConversationEntry.created_at,
                        ConversationEntry.id,
                    )
                )
            ).all()
        )
        summaries = list(
            (
                await db.scalars(
                    select(SummaryArtifact)
                    .where(SummaryArtifact.day_id.in_(day_ids))
                    .order_by(SummaryArtifact.day_id, SummaryArtifact.kind)
                )
            ).all()
        )
        carry_forward_items = list(
            (
                await db.scalars(
                    select(CarryForwardItem)
                    .where(CarryForwardItem.origin_day_id.in_(day_ids))
                    .order_by(
                        CarryForwardItem.origin_day_id,
                        CarryForwardItem.id,
                    )
                )
            ).all()
        )
        if habit_ids:
            habit_logs = list(
                (
                    await db.scalars(
                        select(HabitLog)
                        .where(
                            HabitLog.day_id.in_(day_ids),
                            HabitLog.habit_id.in_(habit_ids),
                        )
                        .order_by(HabitLog.day_id, HabitLog.habit_id)
                    )
                ).all()
            )
        if context_ids:
            day_contexts = list(
                (
                    await db.scalars(
                        select(DayContext)
                        .where(
                            DayContext.day_id.in_(day_ids),
                            DayContext.context_id.in_(context_ids),
                        )
                        .order_by(DayContext.day_id, DayContext.context_id)
                    )
                ).all()
            )
        hour_logs = list(
            (
                await db.scalars(
                    select(HourLog)
                    .where(HourLog.day_id.in_(day_ids))
                    .order_by(HourLog.day_id, HourLog.hour)
                )
            ).all()
        )

    return {
        "format": EXPORT_FORMAT,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "username": user.username,
            "email": user.email,
            "is_verified": user.is_verified,
            "ai_processing_consent": user.ai_processing_consent,
            "ai_redaction_enabled": user.ai_redaction_enabled,
        },
        "resources": {
            "habits": [
                _record(habit, ("id", "name", "is_archived"))
                for habit in habits
            ],
            "contexts": [
                _record(context, ("id", "name", "kind", "is_archived"))
                for context in contexts
            ],
            "days": [
                _record(
                    day,
                    (
                        "id",
                        "date",
                        "status",
                        "daily_note",
                        "created_at",
                        "updated_at",
                    ),
                )
                for day in days
            ],
            "habit_completions": [
                _record(log, ("id", "habit_id", "day_id"))
                for log in habit_logs
            ],
            "day_contexts": [
                _record(link, ("day_id", "context_id"))
                for link in day_contexts
            ],
            "daily_checkins": [
                _record(
                    checkin,
                    (
                        "id",
                        "day_id",
                        "sleep_hours",
                        "sleep_quality",
                        "energy_level",
                        "focus_quality",
                        "emotional_state",
                        "recovery_quality",
                        "reentry_success",
                        "drift_minutes",
                        "notes",
                        "created_at",
                        "updated_at",
                    ),
                )
                for checkin in checkins
            ],
            "conversation_entries": [
                _record(
                    entry,
                    ("id", "day_id", "role", "content", "created_at"),
                )
                for entry in conversations
            ],
            "summary_artifacts": [
                _record(
                    summary,
                    (
                        "id",
                        "day_id",
                        "kind",
                        "content",
                        "provider",
                        "model",
                        "prompt_version",
                        "source_fingerprint",
                        "source_snapshot",
                        "is_user_edited",
                        "generated_at",
                        "updated_at",
                    ),
                )
                for summary in summaries
            ],
            "carry_forward_items": [
                _record(
                    item,
                    (
                        "id",
                        "origin_day_id",
                        "content",
                        "status",
                        "created_at",
                        "resolved_at",
                    ),
                )
                for item in carry_forward_items
            ],
            "weekly_reflections": [
                _record(
                    reflection,
                    (
                        "id",
                        "week_start",
                        "content",
                        "provider",
                        "model",
                        "prompt_version",
                        "source_fingerprint",
                        "source_snapshot",
                        "is_user_edited",
                        "generated_at",
                        "updated_at",
                    ),
                )
                for reflection in weekly_reflections
            ],
            "hour_logs": [
                _record(
                    log,
                    ("id", "day_id", "hour", "content", "updated_at"),
                )
                for log in hour_logs
            ],
            "goals": [
                _record(
                    goal,
                    (
                        "id",
                        "kind",
                        "title",
                        "notes",
                        "sort_order",
                        "created_at",
                        "updated_at",
                    ),
                )
                for goal in goals
            ],
        },
    }

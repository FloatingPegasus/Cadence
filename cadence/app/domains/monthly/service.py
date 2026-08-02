from calendar import monthrange
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.weekly_reflection import WeeklyReflection


def _month_bounds(target_month: str) -> tuple[date, date]:
    if len(target_month) != 7:
        raise ValueError("Month must use YYYY-MM format")
    month_start = datetime.strptime(target_month, "%Y-%m").date().replace(day=1)
    if month_start.strftime("%Y-%m") != target_month:
        raise ValueError("Month must use YYYY-MM format")
    month_end = month_start.replace(
        day=monthrange(month_start.year, month_start.month)[1]
    )
    return month_start, month_end


def _preview(content: str | None, length: int) -> str:
    return " ".join((content or "").split())[:length]


async def get_month(
    db: AsyncSession,
    user_id: int,
    target_month: str,
) -> dict:
    month_start, month_end = _month_bounds(target_month)
    day_result = await db.execute(
        select(Day, DailyCheckin)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= month_start,
            Day.date <= month_end,
        )
        .order_by(Day.date)
    )
    day_rows = day_result.all()
    day_ids = [day.id for day, _ in day_rows]

    habit_counts: dict[int, int] = {}
    conversation_counts: dict[int, int] = {}
    summaries: dict[int, str] = {}
    contexts_by_day: dict[int, list[dict]] = {}
    if day_ids:
        habit_result = await db.execute(
            select(HabitLog.day_id, func.count(HabitLog.id))
            .where(HabitLog.day_id.in_(day_ids))
            .group_by(HabitLog.day_id)
        )
        habit_counts = dict(habit_result.all())

        conversation_result = await db.execute(
            select(
                ConversationEntry.day_id,
                func.count(ConversationEntry.id),
            )
            .where(ConversationEntry.day_id.in_(day_ids))
            .group_by(ConversationEntry.day_id)
        )
        conversation_counts = dict(conversation_result.all())

        summary_result = await db.execute(
            select(SummaryArtifact.day_id, SummaryArtifact.content).where(
                SummaryArtifact.day_id.in_(day_ids),
                SummaryArtifact.kind == "daily",
            )
        )
        summaries = dict(summary_result.all())

        context_result = await db.execute(
            select(
                DayContext.day_id,
                ContinuityContext.id,
                ContinuityContext.name,
                ContinuityContext.kind,
            )
            .join(
                ContinuityContext,
                ContinuityContext.id == DayContext.context_id,
            )
            .where(
                DayContext.day_id.in_(day_ids),
                ContinuityContext.user_id == user_id,
            )
            .order_by(ContinuityContext.name)
        )
        for day_id, context_id, name, kind in context_result.all():
            contexts_by_day.setdefault(day_id, []).append(
                {"id": context_id, "name": name, "kind": kind}
            )

    reflection_result = await db.execute(
        select(WeeklyReflection)
        .where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start >= month_start - timedelta(days=6),
            WeeklyReflection.week_start <= month_end,
        )
        .order_by(WeeklyReflection.week_start)
        .limit(6)
    )
    reflections = list(reflection_result.scalars())

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= month_end,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(20)
    )

    checkin_fields = (
        "sleep_hours",
        "sleep_quality",
        "energy_level",
        "focus_quality",
        "emotional_state",
        "recovery_quality",
        "reentry_success",
        "drift_minutes",
        "notes",
    )
    days = []
    context_stats: dict[int, dict] = {}
    for day, checkin in day_rows:
        note = (day.daily_note or "").strip()
        summary = (summaries.get(day.id) or "").strip()
        contexts = contexts_by_day.get(day.id, [])
        checkin_count = (
            sum(
                getattr(checkin, field) is not None
                for field in checkin_fields
            )
            if checkin
            else 0
        )
        habit_count = habit_counts.get(day.id, 0)
        conversation_count = conversation_counts.get(day.id, 0)
        is_active = any(
            (
                note,
                summary,
                contexts,
                checkin_count,
                habit_count,
                conversation_count,
                day.status == "closed",
            )
        )
        if not is_active:
            continue
        preview = _preview(summary or note, 240)
        days.append(
            {
                "date": day.date.isoformat(),
                "status": day.status,
                "trace_preview": preview,
                "trace_source": (
                    "summary"
                    if summary
                    else "note" if note else None
                ),
                "energy_level": (
                    checkin.energy_level if checkin else None
                ),
                "focus_quality": (
                    checkin.focus_quality if checkin else None
                ),
                "checkin_fields": checkin_count,
                "habit_completions": habit_count,
                "conversation_entries": conversation_count,
                "contexts": contexts,
            }
        )
        for context in contexts:
            current = context_stats.setdefault(
                context["id"],
                {
                    **context,
                    "active_days": 0,
                    "last_date": day.date.isoformat(),
                    "last_trace_preview": "",
                },
            )
            current["active_days"] += 1
            current["last_date"] = day.date.isoformat()
            if preview:
                current["last_trace_preview"] = preview[:180]

    context_movement = sorted(
        context_stats.values(),
        key=lambda item: (item["active_days"], item["last_date"]),
        reverse=True,
    )[:10]

    return {
        "month": target_month,
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "totals": {
            "active_days": len(days),
            "closed_days": sum(
                day["status"] == "closed" for day in days
            ),
            "habit_completions": sum(
                day["habit_completions"] for day in days
            ),
            "weekly_reflections": len(reflections),
        },
        "days": days,
        "weekly_reflections": [
            {
                "id": reflection.id,
                "week_start": reflection.week_start.isoformat(),
                "week_end": (
                    reflection.week_start + timedelta(days=6)
                ).isoformat(),
                "excerpt": _preview(reflection.content, 280),
                "is_user_edited": reflection.is_user_edited,
                "model": reflection.model,
            }
            for reflection in reflections
        ],
        "contexts": context_movement,
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
    }

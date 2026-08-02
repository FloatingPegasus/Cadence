from calendar import monthrange
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact


class ContextMonthNotFoundError(LookupError):
    pass


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


async def get_context_month(
    db: AsyncSession,
    user_id: int,
    context_id: int,
    target_month: str,
) -> dict:
    month_start, month_end = _month_bounds(target_month)
    context = await db.scalar(
        select(ContinuityContext).where(
            ContinuityContext.id == context_id,
            ContinuityContext.user_id == user_id,
        )
    )
    if context is None:
        raise ContextMonthNotFoundError(context_id)

    day_result = await db.execute(
        select(Day, DailyCheckin)
        .join(DayContext, DayContext.day_id == Day.id)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            DayContext.context_id == context_id,
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

    prior_result = await db.execute(
        select(Day, SummaryArtifact.content)
        .join(DayContext, DayContext.day_id == Day.id)
        .outerjoin(
            SummaryArtifact,
            and_(
                SummaryArtifact.day_id == Day.id,
                SummaryArtifact.kind == "daily",
            ),
        )
        .where(
            Day.user_id == user_id,
            DayContext.context_id == context_id,
            Day.date < month_start,
        )
        .order_by(Day.date.desc())
        .limit(1)
    )
    prior_row = prior_result.one_or_none()

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .join(DayContext, DayContext.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            DayContext.context_id == context_id,
            Day.date <= month_end,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(20)
    )

    days = []
    weeks: dict[date, dict] = {}
    for day, checkin in day_rows:
        summary = (summaries.get(day.id) or "").strip()
        note = (day.daily_note or "").strip()
        preview = _preview(summary or note, 240)
        habit_count = habit_counts.get(day.id, 0)
        conversation_count = conversation_counts.get(day.id, 0)
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
                "habit_completions": habit_count,
                "conversation_entries": conversation_count,
            }
        )

        week_start = day.date - timedelta(days=day.date.weekday())
        week = weeks.setdefault(
            week_start,
            {
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "active_days": 0,
                "closed_days": 0,
                "habit_completions": 0,
                "last_date": day.date.isoformat(),
                "last_trace_preview": "",
            },
        )
        week["active_days"] += 1
        week["closed_days"] += day.status == "closed"
        week["habit_completions"] += habit_count
        week["last_date"] = day.date.isoformat()
        if preview:
            week["last_trace_preview"] = preview[:180]

    previous_activity = None
    if prior_row:
        prior_day, prior_summary = prior_row
        summary_preview = _preview(prior_summary, 220)
        note_preview = _preview(prior_day.daily_note, 220)
        previous_activity = {
            "date": prior_day.date.isoformat(),
            "excerpt": summary_preview or note_preview,
            "source": (
                "summary"
                if summary_preview
                else "note" if note_preview else None
            ),
        }

    return {
        "context": {
            "id": context.id,
            "name": context.name,
            "kind": context.kind,
            "is_archived": context.is_archived,
        },
        "month": target_month,
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "totals": {
            "active_days": len(days),
            "closed_days": sum(day["status"] == "closed" for day in days),
            "habit_completions": sum(
                day["habit_completions"] for day in days
            ),
            "conversation_entries": sum(
                day["conversation_entries"] for day in days
            ),
        },
        "previous_activity": previous_activity,
        "weeks": list(weeks.values()),
        "days": days,
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
    }

from calendar import monthrange
from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact


class DisciplineNotFoundError(LookupError):
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


async def get_discipline_month(
    db: AsyncSession,
    user_id: int,
    discipline_id: int,
    target_month: str,
) -> dict:
    month_start, month_end = _month_bounds(target_month)
    discipline = await db.scalar(
        select(Habit).where(
            Habit.id == discipline_id,
            Habit.user_id == user_id,
        )
    )
    if discipline is None:
        raise DisciplineNotFoundError(discipline_id)

    completion_result = await db.execute(
        select(Day, SummaryArtifact.content)
        .join(HabitLog, HabitLog.day_id == Day.id)
        .outerjoin(
            SummaryArtifact,
            and_(
                SummaryArtifact.day_id == Day.id,
                SummaryArtifact.kind == "daily",
            ),
        )
        .where(
            HabitLog.habit_id == discipline_id,
            Day.user_id == user_id,
            Day.date >= month_start,
            Day.date <= month_end,
        )
        .order_by(Day.date)
    )
    completion_rows = completion_result.all()
    day_ids = [day.id for day, _ in completion_rows]

    conversation_counts: dict[int, int] = {}
    context_rows: list[tuple[int, int, str, str]] = []
    if day_ids:
        conversation_result = await db.execute(
            select(
                ConversationEntry.day_id,
                func.count(ConversationEntry.id),
            )
            .where(ConversationEntry.day_id.in_(day_ids))
            .group_by(ConversationEntry.day_id)
        )
        conversation_counts = dict(conversation_result.all())

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
        context_rows = list(context_result.all())

    contexts_by_day: dict[int, list[dict]] = {}
    context_stats: dict[int, dict] = {}
    for day_id, context_id, name, kind in context_rows:
        context = {"id": context_id, "name": name, "kind": kind}
        contexts_by_day.setdefault(day_id, []).append(context)
        current = context_stats.setdefault(
            context_id,
            {**context, "completed_days": 0},
        )
        current["completed_days"] += 1

    previous_result = await db.execute(
        select(Day, SummaryArtifact.content)
        .join(HabitLog, HabitLog.day_id == Day.id)
        .outerjoin(
            SummaryArtifact,
            and_(
                SummaryArtifact.day_id == Day.id,
                SummaryArtifact.kind == "daily",
            ),
        )
        .where(
            HabitLog.habit_id == discipline_id,
            Day.user_id == user_id,
            Day.date < month_start,
        )
        .order_by(Day.date.desc())
        .limit(1)
    )
    previous_row = previous_result.one_or_none()
    previous_completion = None
    if previous_row:
        previous_day, previous_summary = previous_row
        previous_completion = {
            "date": previous_day.date.isoformat(),
            "excerpt": _preview(
                previous_summary or previous_day.daily_note,
                240,
            ),
        }

    days = []
    for day, summary in completion_rows:
        note = (day.daily_note or "").strip()
        summary_preview = _preview(summary, 240)
        note_preview = _preview(note, 240)
        days.append(
            {
                "date": day.date.isoformat(),
                "status": day.status,
                "trace_preview": summary_preview or note_preview,
                "trace_source": (
                    "summary"
                    if summary_preview
                    else "note" if note_preview else None
                ),
                "conversation_entries": conversation_counts.get(day.id, 0),
                "contexts": contexts_by_day.get(day.id, []),
            }
        )

    return {
        "discipline": {
            "id": discipline.id,
            "name": discipline.name,
            "is_archived": discipline.is_archived,
        },
        "month": target_month,
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "totals": {
            "completed_days": len(days),
            "linked_trace_days": sum(
                bool(day["trace_preview"] or day["conversation_entries"])
                for day in days
            ),
            "contexts": len(context_stats),
        },
        "previous_completion": previous_completion,
        "days": days,
        "contexts": sorted(
            context_stats.values(),
            key=lambda context: (context["completed_days"], context["name"]),
            reverse=True,
        ),
    }

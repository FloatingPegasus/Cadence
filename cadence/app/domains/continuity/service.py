from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
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


class ContextFilterNotFoundError(LookupError):
    pass


def _week_bounds(anchor_date: date) -> tuple[date, date]:
    week_start = anchor_date - timedelta(days=anchor_date.weekday())
    return week_start, week_start + timedelta(days=6)


def _like_pattern(term: str) -> str:
    escaped = (
        term.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _excerpt(content: str, term: str, length: int = 220) -> str:
    compact = " ".join(content.split())
    match_at = compact.casefold().find(term.casefold())
    if match_at < 0 or len(compact) <= length:
        return compact[:length]
    start = max(0, match_at - length // 3)
    end = min(len(compact), start + length)
    return (
        ("…" if start else "")
        + compact[start:end]
        + ("…" if end < len(compact) else "")
    )


def _preview(content: str | None, length: int) -> str:
    return " ".join((content or "").split())[:length]


async def get_day_reentry(
    db: AsyncSession,
    user_id: int,
    target_date: date,
) -> dict:
    daily_summary_join = and_(
        SummaryArtifact.day_id == Day.id,
        SummaryArtifact.kind == "daily",
    )
    previous_result = await db.execute(
        select(
            Day.date,
            Day.daily_note,
            SummaryArtifact.content,
        )
        .outerjoin(SummaryArtifact, daily_summary_join)
        .where(
            Day.user_id == user_id,
            Day.date < target_date,
            or_(
                func.length(func.trim(func.coalesce(Day.daily_note, ""))) > 0,
                func.length(
                    func.trim(func.coalesce(SummaryArtifact.content, ""))
                )
                > 0,
            ),
        )
        .order_by(Day.date.desc())
        .limit(1)
    )
    previous_row = previous_result.one_or_none()
    previous_trace = None
    if previous_row:
        previous_date, daily_note, summary = previous_row
        summary_preview = _preview(summary, 280)
        previous_trace = {
            "date": previous_date.isoformat(),
            "source": "summary" if summary_preview else "note",
            "excerpt": summary_preview or _preview(daily_note, 280),
        }

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= target_date,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(3)
    )

    context_result = await db.execute(
        select(
            ContinuityContext.id,
            ContinuityContext.name,
            ContinuityContext.kind,
        )
        .join(
            DayContext,
            DayContext.context_id == ContinuityContext.id,
        )
        .join(Day, Day.id == DayContext.day_id)
        .where(
            Day.user_id == user_id,
            Day.date == target_date,
            ContinuityContext.user_id == user_id,
        )
        .order_by(ContinuityContext.name)
        .limit(4)
    )
    context_rows = context_result.all()
    context_ids = [context_id for context_id, _, _ in context_rows]
    activities: dict[int, dict] = {}
    if context_ids:
        ranked_days = (
            select(
                DayContext.context_id.label("context_id"),
                Day.id.label("day_id"),
                Day.date.label("activity_date"),
                Day.daily_note.label("daily_note"),
                func.row_number()
                .over(
                    partition_by=DayContext.context_id,
                    order_by=Day.date.desc(),
                )
                .label("position"),
            )
            .join(Day, Day.id == DayContext.day_id)
            .where(
                Day.user_id == user_id,
                Day.date < target_date,
                DayContext.context_id.in_(context_ids),
            )
            .subquery()
        )
        activity_result = await db.execute(
            select(
                ranked_days.c.context_id,
                ranked_days.c.activity_date,
                ranked_days.c.daily_note,
                SummaryArtifact.content,
            )
            .outerjoin(
                SummaryArtifact,
                and_(
                    SummaryArtifact.day_id == ranked_days.c.day_id,
                    SummaryArtifact.kind == "daily",
                ),
            )
            .where(ranked_days.c.position == 1)
        )
        for context_id, activity_date, daily_note, summary in (
            activity_result.all()
        ):
            summary_preview = _preview(summary, 180)
            note_preview = _preview(daily_note, 180)
            activities[context_id] = {
                "date": activity_date.isoformat(),
                "source": (
                    "summary"
                    if summary_preview
                    else "note" if note_preview else None
                ),
                "excerpt": summary_preview or note_preview,
            }

    return {
        "date": target_date.isoformat(),
        "previous_trace": previous_trace,
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
        "contexts": [
            {
                "id": context_id,
                "name": name,
                "kind": kind,
                "last_activity": activities.get(context_id),
            }
            for context_id, name, kind in context_rows
        ],
    }


async def get_week(
    db: AsyncSession,
    user_id: int,
    anchor_date: date,
) -> dict:
    week_start, week_end = _week_bounds(anchor_date)

    day_result = await db.execute(
        select(Day, DailyCheckin)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
        )
        .order_by(Day.date)
    )
    day_rows = {
        day.date: (day, checkin)
        for day, checkin in day_result.all()
    }

    habit_result = await db.execute(
        select(Day.date, func.count(HabitLog.id))
        .join(HabitLog, HabitLog.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
        )
        .group_by(Day.date)
    )
    habit_counts = dict(habit_result.all())

    summary_result = await db.execute(
        select(Day.date, SummaryArtifact.content)
        .join(SummaryArtifact, SummaryArtifact.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
            SummaryArtifact.kind == "daily",
        )
    )
    summaries = dict(summary_result.all())

    context_result = await db.execute(
        select(
            Day.date,
            ContinuityContext.id,
            ContinuityContext.name,
            ContinuityContext.kind,
        )
        .join(DayContext, DayContext.day_id == Day.id)
        .join(
            ContinuityContext,
            ContinuityContext.id == DayContext.context_id,
        )
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
            ContinuityContext.user_id == user_id,
        )
        .order_by(Day.date, ContinuityContext.name)
    )
    contexts_by_date: dict[date, list[dict]] = {}
    for context_date, context_id, name, kind in context_result.all():
        contexts_by_date.setdefault(context_date, []).append(
            {"id": context_id, "name": name, "kind": kind}
        )

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= week_end,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date, CarryForwardItem.created_at)
        .limit(20)
    )

    days = []
    for offset in range(7):
        current_date = week_start + timedelta(days=offset)
        day, checkin = day_rows.get(current_date, (None, None))
        daily_note = (day.daily_note or "").strip() if day else ""
        summary = (summaries.get(current_date) or "").strip()
        days.append(
            {
                "date": current_date.isoformat(),
                "has_entry": day is not None,
                "status": day.status if day else None,
                "note_preview": daily_note[:180],
                "summary_preview": summary[:240],
                "energy_level": (
                    checkin.energy_level if checkin else None
                ),
                "focus_quality": (
                    checkin.focus_quality if checkin else None
                ),
                "habit_completions": habit_counts.get(current_date, 0),
                "contexts": contexts_by_date.get(current_date, []),
            }
        )

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "totals": {
            "active_days": len(day_rows),
            "closed_days": sum(
                1 for day, _ in day_rows.values() if day.status == "closed"
            ),
            "habit_completions": sum(habit_counts.values()),
        },
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


async def search(
    db: AsyncSession,
    user_id: int,
    term: str,
    start_date: date,
    end_date: date,
    source: str = "all",
    limit: int = 20,
    context_id: int | None = None,
) -> dict:
    pattern = _like_pattern(term)
    results: list[dict] = []
    context_day_ids: list[int] | None = None

    if context_id is not None:
        context_exists = await db.scalar(
            select(ContinuityContext.id).where(
                ContinuityContext.id == context_id,
                ContinuityContext.user_id == user_id,
            )
        )
        if context_exists is None:
            raise ContextFilterNotFoundError(context_id)
        day_id_result = await db.execute(
            select(Day.id)
            .join(DayContext, DayContext.day_id == Day.id)
            .where(
                Day.user_id == user_id,
                Day.date >= start_date,
                Day.date <= end_date,
                DayContext.context_id == context_id,
            )
        )
        context_day_ids = list(day_id_result.scalars())

    if context_day_ids == []:
        return {
            "query": term,
            "source": source,
            "context_id": context_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "results": [],
        }

    if source in {"all", "notes"}:
        note_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            Day.daily_note.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            note_filters.append(Day.id.in_(context_day_ids))
        note_result = await db.execute(
            select(Day)
            .where(*note_filters)
            .order_by(Day.date.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "notes",
                "source_id": day.id,
                "date": day.date.isoformat(),
                "title": "Daily note",
                "excerpt": _excerpt(day.daily_note or "", term),
                "_sort_at": (
                    day.updated_at.isoformat() if day.updated_at else ""
                ),
            }
            for day in note_result.scalars()
        )

    if source in {"all", "conversation"}:
        conversation_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            ConversationEntry.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            conversation_filters.append(Day.id.in_(context_day_ids))
        conversation_result = await db.execute(
            select(ConversationEntry, Day.date)
            .join(Day, Day.id == ConversationEntry.day_id)
            .where(*conversation_filters)
            .order_by(Day.date.desc(), ConversationEntry.created_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "conversation",
                "source_id": entry.id,
                "date": entry_date.isoformat(),
                "title": "Conversation entry",
                "excerpt": _excerpt(entry.content, term),
                "_sort_at": entry.created_at.isoformat(),
            }
            for entry, entry_date in conversation_result.all()
        )

    if source in {"all", "summaries"}:
        summary_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            SummaryArtifact.kind == "daily",
            SummaryArtifact.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            summary_filters.append(Day.id.in_(context_day_ids))
        summary_result = await db.execute(
            select(SummaryArtifact, Day.date)
            .join(Day, Day.id == SummaryArtifact.day_id)
            .where(*summary_filters)
            .order_by(Day.date.desc(), SummaryArtifact.updated_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "summaries",
                "source_id": artifact.id,
                "date": summary_date.isoformat(),
                "title": "Daily summary",
                "excerpt": _excerpt(artifact.content, term),
                "_sort_at": artifact.updated_at.isoformat(),
            }
            for artifact, summary_date in summary_result.all()
        )

    if source in {"all", "threads"}:
        thread_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            CarryForwardItem.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            thread_filters.append(Day.id.in_(context_day_ids))
        thread_result = await db.execute(
            select(CarryForwardItem, Day.date)
            .join(Day, Day.id == CarryForwardItem.origin_day_id)
            .where(*thread_filters)
            .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "threads",
                "source_id": item.id,
                "date": origin_date.isoformat(),
                "title": "Carry-forward thread",
                "excerpt": _excerpt(item.content, term),
                "status": item.status,
                "_sort_at": item.created_at.isoformat(),
            }
            for item, origin_date in thread_result.all()
        )

    if context_id is None and source in {"all", "weekly_reflections"}:
        reflection_result = await db.execute(
            select(WeeklyReflection)
            .where(
                WeeklyReflection.user_id == user_id,
                WeeklyReflection.week_start >= start_date,
                WeeklyReflection.week_start <= end_date,
                WeeklyReflection.content.ilike(pattern, escape="\\"),
            )
            .order_by(
                WeeklyReflection.week_start.desc(),
                WeeklyReflection.updated_at.desc(),
            )
            .limit(limit)
        )
        results.extend(
            {
                "source": "weekly_reflections",
                "source_id": reflection.id,
                "date": reflection.week_start.isoformat(),
                "title": "Weekly reflection",
                "excerpt": _excerpt(reflection.content, term),
                "_sort_at": reflection.updated_at.isoformat(),
            }
            for reflection in reflection_result.scalars()
        )

    results.sort(
        key=lambda item: (item["date"], item["_sort_at"]),
        reverse=True,
    )
    bounded = results[:limit]
    for item in bounded:
        item.pop("_sort_at", None)

    return {
        "query": term,
        "source": source,
        "context_id": context_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "results": bounded,
    }

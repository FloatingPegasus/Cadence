from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..days.service import get_or_create_day
from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...services.continuity_lock import acquire_continuity_lock


class ContextNotFoundError(LookupError):
    pass


class ContextNameConflictError(ValueError):
    pass


def serialize(context: ContinuityContext) -> dict:
    return {
        "id": context.id,
        "name": context.name,
        "kind": context.kind,
        "is_archived": context.is_archived,
    }


async def list_contexts(
    db: AsyncSession,
    user_id: int,
    include_archived: bool = False,
) -> list[dict]:
    query = select(ContinuityContext).where(
        ContinuityContext.user_id == user_id
    )
    if not include_archived:
        query = query.where(ContinuityContext.is_archived.is_(False))
    result = await db.execute(query.order_by(ContinuityContext.id))
    return [serialize(context) for context in result.scalars()]


async def create_context(
    db: AsyncSession,
    user_id: int,
    name: str,
    kind: str,
) -> dict:
    context = ContinuityContext(
        user_id=user_id,
        name=name,
        kind=kind,
        is_archived=False,
    )
    db.add(context)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ContextNameConflictError(name) from error
    await db.refresh(context)
    return serialize(context)


async def update_context(
    db: AsyncSession,
    user_id: int,
    context_id: int,
    name: str,
    kind: str,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    context = await db.scalar(
        select(ContinuityContext).where(
            ContinuityContext.id == context_id,
            ContinuityContext.user_id == user_id,
            ContinuityContext.is_archived.is_(False),
        )
    )
    if context is None:
        raise ContextNotFoundError(context_id)
    context.name = name
    context.kind = kind
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ContextNameConflictError(name) from error
    await db.refresh(context)
    return serialize(context)


async def archive_context(
    db: AsyncSession,
    user_id: int,
    context_id: int,
) -> dict:
    context = await db.scalar(
        select(ContinuityContext).where(
            ContinuityContext.id == context_id,
            ContinuityContext.user_id == user_id,
            ContinuityContext.is_archived.is_(False),
        )
    )
    if context is None:
        raise ContextNotFoundError(context_id)
    context.is_archived = True
    await db.commit()
    await db.refresh(context)
    return serialize(context)


async def list_for_day(
    db: AsyncSession,
    user_id: int,
    target_date: date,
) -> list[dict]:
    result = await db.execute(
        select(ContinuityContext)
        .join(DayContext, DayContext.context_id == ContinuityContext.id)
        .join(Day, Day.id == DayContext.day_id)
        .where(
            Day.user_id == user_id,
            Day.date == target_date,
            ContinuityContext.user_id == user_id,
        )
        .order_by(ContinuityContext.name)
    )
    return [serialize(context) for context in result.scalars()]


async def set_for_day(
    db: AsyncSession,
    user_id: int,
    target_date: date,
    context_ids: list[int],
) -> list[dict]:
    await acquire_continuity_lock(db, user_id)
    unique_ids = list(dict.fromkeys(context_ids))
    day = await db.scalar(
        select(Day).where(
            Day.user_id == user_id,
            Day.date == target_date,
        )
    )
    existing_ids: set[int] = set()
    if day is not None:
        existing_result = await db.execute(
            select(DayContext.context_id).where(DayContext.day_id == day.id)
        )
        existing_ids = set(existing_result.scalars())
    contexts: list[ContinuityContext] = []
    if unique_ids:
        result = await db.execute(
            select(ContinuityContext).where(
                ContinuityContext.id.in_(unique_ids),
                ContinuityContext.user_id == user_id,
            )
        )
        contexts = list(result.scalars())
        unavailable = len(contexts) != len(unique_ids) or any(
            context.is_archived and context.id not in existing_ids
            for context in contexts
        )
        if unavailable:
            raise ContextNotFoundError("One or more contexts are unavailable")

    if day is None:
        day = await get_or_create_day(db, user_id, target_date)

    await db.execute(delete(DayContext).where(DayContext.day_id == day.id))
    db.add_all(
        DayContext(day_id=day.id, context_id=context.id)
        for context in contexts
    )
    await db.commit()
    contexts.sort(key=lambda context: context.name.casefold())
    return [serialize(context) for context in contexts]


async def get_continuity(
    db: AsyncSession,
    user_id: int,
    context_id: int,
    limit: int = 12,
) -> dict:
    context = await db.scalar(
        select(ContinuityContext).where(
            ContinuityContext.id == context_id,
            ContinuityContext.user_id == user_id,
        )
    )
    if context is None:
        raise ContextNotFoundError(context_id)

    day_result = await db.execute(
        select(Day, DailyCheckin)
        .join(DayContext, DayContext.day_id == Day.id)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            DayContext.context_id == context_id,
        )
        .order_by(Day.date.desc())
        .limit(limit)
    )
    day_rows = day_result.all()
    day_ids = [day.id for day, _ in day_rows]

    habit_counts: dict[int, int] = {}
    summaries: dict[int, str] = {}
    if day_ids:
        habit_result = await db.execute(
            select(HabitLog.day_id, func.count(HabitLog.id))
            .where(HabitLog.day_id.in_(day_ids))
            .group_by(HabitLog.day_id)
        )
        habit_counts = dict(habit_result.all())

        summary_result = await db.execute(
            select(SummaryArtifact.day_id, SummaryArtifact.content).where(
                SummaryArtifact.day_id.in_(day_ids),
                SummaryArtifact.kind == "daily",
            )
        )
        summaries = dict(summary_result.all())

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .join(DayContext, DayContext.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            DayContext.context_id == context_id,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(20)
    )

    return {
        "context": serialize(context),
        "recent_days": [
            {
                "date": day.date.isoformat(),
                "status": day.status,
                "note_preview": (day.daily_note or "").strip()[:180],
                "summary_preview": (
                    summaries.get(day.id) or ""
                ).strip()[:240],
                "energy_level": (
                    checkin.energy_level if checkin else None
                ),
                "focus_quality": (
                    checkin.focus_quality if checkin else None
                ),
                "habit_completions": habit_counts.get(day.id, 0),
            }
            for day, checkin in day_rows
        ],
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
    }

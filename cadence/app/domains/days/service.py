from datetime import date, datetime, timezone

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.day import Day
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.day_context import DayContext
from ...services import embeddings as embedding_service
from ...services.continuity_lock import acquire_continuity_lock


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def get_or_create_day(
    db: AsyncSession, user_id: int, target_date: date | str
) -> Day:
    day_date = _coerce_date(target_date)
    statement = pg_insert(Day).values(
        user_id=user_id,
        date=day_date,
    ).on_conflict_do_nothing(
        index_elements=[Day.user_id, Day.date]
    ).returning(Day.id)
    result = await db.execute(statement)
    day_id = result.scalar_one_or_none()
    if day_id is None:
        day_id = await db.scalar(
            select(Day.id).where(
                Day.user_id == user_id,
                Day.date == day_date,
            )
        )
    if day_id is None:
        raise RuntimeError("day disappeared while being created")
    day = await db.get(Day, day_id)
    if day is None:
        raise RuntimeError("day disappeared while being loaded")
    return day


async def get_day(db: AsyncSession, user_id: int, target_date: date | str) -> dict:
    day_date = _coerce_date(target_date)
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    return {
        "id": day.id if day else None,
        "date": day_date.isoformat(),
        "status": day.status if day else "open",
        "daily_note": day.daily_note if day else "",
    }


async def list_recent_days(
    db: AsyncSession, user_id: int, limit: int = 7
) -> list[dict]:
    checkin_has_values = or_(
        DailyCheckin.sleep_hours.is_not(None),
        DailyCheckin.sleep_quality.is_not(None),
        DailyCheckin.energy_level.is_not(None),
        DailyCheckin.focus_quality.is_not(None),
        DailyCheckin.emotional_state.is_not(None),
        DailyCheckin.recovery_quality.is_not(None),
        DailyCheckin.reentry_success.is_not(None),
        DailyCheckin.drift_minutes.is_not(None),
        DailyCheckin.notes.is_not(None),
    )
    has_activity = or_(
        Day.status == "closed",
        func.length(func.trim(func.coalesce(Day.daily_note, ""))) > 0,
        checkin_has_values,
        exists(
            select(ConversationEntry.id).where(
                ConversationEntry.day_id == Day.id,
                func.length(func.trim(ConversationEntry.content)) > 0,
            )
        ),
        exists(
            select(HabitLog.id).where(HabitLog.day_id == Day.id)
        ),
        exists(
            select(SummaryArtifact.id).where(
                SummaryArtifact.day_id == Day.id,
                SummaryArtifact.kind == "daily",
                func.length(func.trim(SummaryArtifact.content)) > 0,
            )
        ),
        exists(
            select(CarryForwardItem.id).where(
                CarryForwardItem.origin_day_id == Day.id
            )
        ),
        exists(select(DayContext.day_id).where(DayContext.day_id == Day.id)),
    )
    result = await db.execute(
        select(Day, DailyCheckin)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(Day.user_id == user_id, has_activity)
        .order_by(Day.date.desc())
        .limit(limit)
    )
    return [
        {
            "id": day.id,
            "date": day.date.isoformat(),
            "status": day.status,
            "note_preview": (day.daily_note or "").strip()[:160],
            "energy_level": checkin.energy_level if checkin else None,
            "focus_quality": checkin.focus_quality if checkin else None,
        }
        for day, checkin in result.all()
    ]


async def update_day(
    db: AsyncSession, user_id: int, target_date: date | str, daily_note: str
) -> dict:
    await acquire_continuity_lock(db, user_id)
    day = await get_or_create_day(db, user_id, target_date)
    day.daily_note = daily_note
    await db.commit()
    await db.refresh(day)
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="notes",
        source_id=day.id,
        day_id=day.id,
        source_date=day.date,
        content=day.daily_note or "",
    )
    return {
        "id": day.id,
        "date": day.date.isoformat(),
        "status": day.status,
        "daily_note": day.daily_note or "",
    }


async def update_day_status(
    db: AsyncSession, user_id: int, target_date: date | str, status: str
) -> dict:
    await acquire_continuity_lock(db, user_id)
    day = await get_or_create_day(db, user_id, target_date)
    day.status = status
    await db.commit()
    await db.refresh(day)
    return {
        "id": day.id,
        "date": day.date.isoformat(),
        "status": day.status,
        "daily_note": day.daily_note or "",
    }


async def get_closure_preview(
    db: AsyncSession,
    user_id: int,
    target_date: date | str,
) -> dict:
    day_date = _coerce_date(target_date)
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    if day is None:
        return {
            "date": day_date.isoformat(),
            "status": "open",
            "capture": {
                "has_daily_note": False,
                "conversation_entries": 0,
                "completed_habits": 0,
                "checkin_fields": 0,
            },
            "summary": {
                "exists": False,
                "excerpt": "",
                "is_user_edited": False,
            },
            "open_thread_count": 0,
            "open_threads": [],
        }
    counts_result = await db.execute(
        select(
            select(func.count(ConversationEntry.id))
            .where(ConversationEntry.day_id == day.id)
            .scalar_subquery(),
            select(func.count(HabitLog.id))
            .where(HabitLog.day_id == day.id)
            .scalar_subquery(),
        )
    )
    conversation_entries, completed_habits = counts_result.one()

    capture_result = await db.execute(
        select(DailyCheckin, SummaryArtifact)
        .select_from(Day)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .outerjoin(
            SummaryArtifact,
            and_(
                SummaryArtifact.day_id == Day.id,
                SummaryArtifact.kind == "daily",
            ),
        )
        .where(Day.id == day.id, Day.user_id == user_id)
    )
    checkin, summary = capture_result.one()
    checkin_fields = (
        sum(
            getattr(checkin, field) is not None
            for field in (
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
        )
        if checkin
        else 0
    )

    thread_result = await db.execute(
        select(
            CarryForwardItem,
            Day.date,
            func.count().over().label("total_count"),
        )
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= day.date,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(5)
    )
    thread_rows = thread_result.all()

    return {
        "date": day.date.isoformat(),
        "status": day.status,
        "capture": {
            "has_daily_note": bool((day.daily_note or "").strip()),
            "conversation_entries": conversation_entries,
            "completed_habits": completed_habits,
            "checkin_fields": checkin_fields,
        },
        "summary": (
            {
                "exists": True,
                "excerpt": " ".join(summary.content.split())[:280],
                "is_user_edited": summary.is_user_edited,
            }
            if summary
            else {
                "exists": False,
                "excerpt": "",
                "is_user_edited": False,
            }
        ),
        "open_thread_count": (
            thread_rows[0].total_count if thread_rows else 0
        ),
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date, _ in thread_rows
        ],
    }


async def get_day_context(
    db: AsyncSession, user_id: int, target_date: date | str
) -> dict:
    day_date = _coerce_date(target_date)
    result = await db.execute(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    day = result.scalar_one_or_none()

    result = await db.execute(
        select(Day)
        .where(Day.user_id == user_id, Day.date < day_date)
        .order_by(Day.date.desc())
        .limit(1)
    )
    prev_day = result.scalar_one_or_none()

    return {
        "day": {
            "id": day.id if day else None,
            "date": day_date.isoformat(),
            "daily_note": day.daily_note if day else "",
        },
        "previous_day": prev_day.date.isoformat() if prev_day else None,
    }


async def get_checkin(
    db: AsyncSession, user_id: int, target_date: date | str
) -> dict:
    day_date = _coerce_date(target_date)
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    if day is None:
        return {}
    result = await db.execute(
        select(DailyCheckin).where(DailyCheckin.day_id == day.id)
    )
    checkin = result.scalar_one_or_none()
    if not checkin:
        return {}
    return {
        "sleep_hours": checkin.sleep_hours,
        "sleep_quality": checkin.sleep_quality,
        "energy_level": checkin.energy_level,
        "focus_quality": checkin.focus_quality,
        "emotional_state": checkin.emotional_state,
        "recovery_quality": checkin.recovery_quality,
        "reentry_success": checkin.reentry_success,
        "drift_minutes": checkin.drift_minutes,
        "notes": checkin.notes,
    }


async def update_checkin(
    db: AsyncSession, user_id: int, target_date: date | str, data: dict
) -> dict:
    await acquire_continuity_lock(db, user_id)
    day_date = _coerce_date(target_date)
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    if day is None and not data:
        return {}
    if day is None:
        day = await get_or_create_day(db, user_id, target_date)
    result = await db.execute(
        select(DailyCheckin).where(DailyCheckin.day_id == day.id)
    )
    checkin = result.scalar_one_or_none()
    if not checkin:
        checkin = DailyCheckin(day_id=day.id)
        db.add(checkin)
    for field, value in data.items():
        setattr(checkin, field, value)
    await db.commit()
    await db.refresh(checkin)
    return {
        "sleep_hours": checkin.sleep_hours,
        "sleep_quality": checkin.sleep_quality,
        "energy_level": checkin.energy_level,
        "focus_quality": checkin.focus_quality,
        "emotional_state": checkin.emotional_state,
        "recovery_quality": checkin.recovery_quality,
        "reentry_success": checkin.reentry_success,
        "drift_minutes": checkin.drift_minutes,
        "notes": checkin.notes,
    }


async def list_conversation(
    db: AsyncSession, user_id: int, target_date: date | str
) -> list[dict]:
    day_date = _coerce_date(target_date)
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    if day is None:
        return []
    result = await db.execute(
        select(ConversationEntry)
        .where(ConversationEntry.day_id == day.id)
        .order_by(ConversationEntry.created_at)
    )
    return [
        {
            "id": e.id,
            "role": e.role,
            "content": e.content,
            "created_at": _utc_iso(e.created_at),
        }
        for e in result.scalars().all()
    ]


async def add_conversation_entry(
    db: AsyncSession,
    user_id: int,
    target_date: date | str,
    content: str,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    day = await get_or_create_day(db, user_id, target_date)
    entry = ConversationEntry(day_id=day.id, role="user", content=content.strip())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="conversation",
        source_id=entry.id,
        day_id=day.id,
        source_date=day.date,
        content=entry.content,
    )
    return {
        "id": entry.id,
        "role": entry.role,
        "content": entry.content,
        "created_at": _utc_iso(entry.created_at),
    }

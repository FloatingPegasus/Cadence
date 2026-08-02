from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.day import Day
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


async def get_or_create_day(
    db: AsyncSession, user_id: int, target_date: date | str
) -> Day:
    day_date = _coerce_date(target_date)
    result = await db.execute(
        select(Day).where(Day.user_id == user_id, Day.date == day_date)
    )
    day = result.scalar_one_or_none()
    if not day:
        day = Day(user_id=user_id, date=day_date)
        db.add(day)
        try:
            await db.commit()
            await db.refresh(day)
        except IntegrityError:
            # Multiple parts of the daily panel load in parallel. If another
            # request created the same per-user Day after our initial SELECT,
            # reuse that canonical row.
            await db.rollback()
            result = await db.execute(
                select(Day).where(
                    Day.user_id == user_id, Day.date == day_date
                )
            )
            day = result.scalar_one_or_none()
            if day is None:
                raise
    return day


async def get_day(db: AsyncSession, user_id: int, target_date: date | str) -> dict:
    day = await get_or_create_day(db, user_id, target_date)
    return {
        "id": day.id,
        "date": day.date.isoformat(),
        "status": day.status,
        "daily_note": day.daily_note or "",
    }


async def list_recent_days(
    db: AsyncSession, user_id: int, limit: int = 7
) -> list[dict]:
    result = await db.execute(
        select(Day, DailyCheckin)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(Day.user_id == user_id)
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
    day = await get_or_create_day(db, user_id, target_date)
    day.daily_note = daily_note
    await db.commit()
    await db.refresh(day)
    return {
        "id": day.id,
        "date": day.date.isoformat(),
        "status": day.status,
        "daily_note": day.daily_note or "",
    }


async def update_day_status(
    db: AsyncSession, user_id: int, target_date: date | str, status: str
) -> dict:
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
    day = await get_or_create_day(db, user_id, target_date)
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
    day = await get_or_create_day(db, user_id, target_date)
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
    day = await get_or_create_day(db, user_id, target_date)
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
            "created_at": e.created_at.isoformat(),
        }
        for e in result.scalars().all()
    ]


async def add_conversation_entry(
    db: AsyncSession,
    user_id: int,
    target_date: date | str,
    content: str,
) -> dict:
    day = await get_or_create_day(db, user_id, target_date)
    entry = ConversationEntry(day_id=day.id, role="user", content=content.strip())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {
        "id": entry.id,
        "role": entry.role,
        "content": entry.content,
        "created_at": entry.created_at.isoformat(),
    }

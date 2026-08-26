from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..days.service import get_or_create_day
from ...persistence.models.day import Day
from ...persistence.models.hour_log import HourLog
from ...services.continuity_lock import acquire_continuity_lock


def _serialize_slot(hour: int, content: str) -> dict:
    return {"hour": hour, "content": content}


async def list_hours(
    db: AsyncSession, user_id: int, target_date: date
) -> list[dict]:
    day = await db.scalar(
        select(Day).where(Day.user_id == user_id, Day.date == target_date)
    )
    filled: dict[int, str] = {}
    if day is not None:
        rows = await db.scalars(
            select(HourLog)
            .where(HourLog.day_id == day.id)
            .order_by(HourLog.hour)
        )
        filled = {row.hour: row.content for row in rows}
    return [_serialize_slot(hour, filled.get(hour, "")) for hour in range(24)]


async def upsert_hour(
    db: AsyncSession,
    user_id: int,
    target_date: date,
    hour: int,
    content: str,
) -> dict:
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    normalized = content.strip()
    await acquire_continuity_lock(db, user_id)
    day = await get_or_create_day(db, user_id, target_date)
    if not normalized:
        existing = await db.scalar(
            select(HourLog).where(
                HourLog.day_id == day.id,
                HourLog.hour == hour,
            )
        )
        if existing is not None:
            await db.delete(existing)
            await db.commit()
        return _serialize_slot(hour, "")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    statement = pg_insert(HourLog).values(
        day_id=day.id,
        hour=hour,
        content=normalized,
        updated_at=now,
    )
    statement = statement.on_conflict_do_update(
        constraint="day_hour_uc",
        set_={
            "content": statement.excluded.content,
            "updated_at": statement.excluded.updated_at,
        },
    )
    await db.execute(statement)
    await db.commit()
    return _serialize_slot(hour, normalized)

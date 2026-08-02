from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..days.service import get_or_create_day
from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.day import Day
from ...services.ai import utcnow


class CarryForwardNotFoundError(LookupError):
    pass


def serialize(item: CarryForwardItem, origin_date: date) -> dict:
    return {
        "id": item.id,
        "origin_date": origin_date.isoformat(),
        "content": item.content,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "resolved_at": (
            item.resolved_at.isoformat() if item.resolved_at else None
        ),
    }


async def list_for_day(
    db: AsyncSession, user_id: int, target_date: date
) -> list[dict]:
    result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= target_date,
            or_(
                CarryForwardItem.status == "open",
                and_(
                    Day.date == target_date,
                    CarryForwardItem.status != "open",
                ),
            ),
        )
        .order_by(
            CarryForwardItem.status != "open",
            Day.date,
            CarryForwardItem.created_at,
        )
    )
    return [serialize(item, origin_date) for item, origin_date in result.all()]


async def create_item(
    db: AsyncSession, user_id: int, target_date: date, content: str
) -> dict:
    day = await get_or_create_day(db, user_id, target_date)
    item = CarryForwardItem(
        origin_day_id=day.id, content=content.strip(), status="open"
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return serialize(item, day.date)


async def update_status(
    db: AsyncSession, user_id: int, item_id: int, status: str
) -> dict:
    result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            CarryForwardItem.id == item_id,
            Day.user_id == user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise CarryForwardNotFoundError(item_id)
    item, origin_date = row
    item.status = status
    item.resolved_at = None if status == "open" else utcnow()
    await db.commit()
    await db.refresh(item)
    return serialize(item, origin_date)

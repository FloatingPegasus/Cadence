import calendar
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.day import Day
from ...services.continuity_lock import acquire_continuity_lock


class HabitNotFoundError(LookupError):
    """Raised when a habit is not owned by the requesting user."""


class HabitNameConflictError(ValueError):
    """Raised when an active habit already uses the requested name."""


def _habit_dict(habit: Habit) -> dict:
    return {
        "id": habit.id,
        "name": habit.name,
        "is_archived": habit.is_archived,
    }


async def list_habits(
    db: AsyncSession, user_id: int, include_archived: bool = False
) -> list[dict]:
    query = select(Habit).where(Habit.user_id == user_id)
    if not include_archived:
        query = query.where(Habit.is_archived.is_(False))
    result = await db.execute(query.order_by(Habit.id))
    return [_habit_dict(habit) for habit in result.scalars().all()]


async def get_day_habits(
    db: AsyncSession, user_id: int, target_date: date
) -> list[dict]:
    result = await db.execute(
        select(Habit)
        .where(Habit.user_id == user_id, Habit.is_archived.is_(False))
        .order_by(Habit.id)
    )
    habits = list(result.scalars().all())
    day_id = await db.scalar(
        select(Day.id).where(Day.user_id == user_id, Day.date == target_date)
    )
    completed_ids: set[int] = set()
    if day_id is not None:
        logged = await db.execute(
            select(HabitLog.habit_id).where(HabitLog.day_id == day_id)
        )
        completed_ids = set(logged.scalars().all())
    return [
        {**_habit_dict(habit), "completed": habit.id in completed_ids}
        for habit in habits
    ]


async def create_habit(db: AsyncSession, user_id: int, name: str) -> dict:
    habit = Habit(user_id=user_id, name=name, is_archived=False)
    db.add(habit)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HabitNameConflictError(name) from error
    await db.refresh(habit)
    return _habit_dict(habit)


async def rename_habit(
    db: AsyncSession, user_id: int, habit_id: int, name: str
) -> dict:
    await acquire_continuity_lock(db, user_id)
    result = await db.execute(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == user_id,
            Habit.is_archived.is_(False),
        )
    )
    habit = result.scalar_one_or_none()
    if habit is None:
        raise HabitNotFoundError(habit_id)
    habit.name = name
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HabitNameConflictError(name) from error
    await db.refresh(habit)
    return _habit_dict(habit)


async def archive_habit(
    db: AsyncSession, user_id: int, habit_id: int
) -> dict:
    result = await db.execute(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == user_id,
            Habit.is_archived.is_(False),
        )
    )
    habit = result.scalar_one_or_none()
    if habit is None:
        raise HabitNotFoundError(habit_id)
    habit.is_archived = True
    await db.commit()
    await db.refresh(habit)
    return _habit_dict(habit)


async def get_month_data(
    db: AsyncSession, user_id: int, month: str
) -> dict:
    view_date = datetime.strptime(month, "%Y-%m").date()
    first = view_date.replace(day=1)
    num_days = calendar.monthrange(view_date.year, view_date.month)[1]
    last = date(view_date.year, view_date.month, num_days)
    day_list = [date(view_date.year, view_date.month, d) for d in range(1, num_days + 1)]

    result = await db.execute(
        select(Habit).where(Habit.user_id == user_id).order_by(Habit.id)
    )
    habits = result.scalars().all()

    result = await db.execute(
        select(HabitLog.habit_id, Day.date)
        .join(Day, Day.id == HabitLog.day_id)
        .where(
            Day.user_id == user_id,
            Day.date >= first,
            Day.date <= last,
        )
    )
    logs = result.all()
    logged_habit_ids = {habit_id for habit_id, _ in logs}
    visible_habits = [
        habit
        for habit in habits
        if not habit.is_archived or habit.id in logged_habit_ids
    ]
    lookup = {
        (habit_id, log_date.strftime("%Y-%m-%d")): True
        for habit_id, log_date in logs
    }

    return {
        "month": month,
        "num_days": num_days,
        "days": [d.day for d in day_list],
        "habits": [_habit_dict(habit) for habit in visible_habits],
        "lookup": {f"{h[0]}-{h[1]}": True for h in lookup},
    }


async def toggle_habit(
    db: AsyncSession,
    user_id: int,
    habit_id: int,
    log_date: date,
    value: str,
) -> None:
    habit_result = await db.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
        .where(Habit.is_archived.is_(False))
    )
    if habit_result.scalar_one_or_none() is None:
        raise HabitNotFoundError(habit_id)

    if value not in {"0", "1"}:
        raise ValueError("Habit value must be '0' or '1'")

    await acquire_continuity_lock(db, user_id)

    if value == "0":
        day_id = await db.scalar(
            select(Day.id).where(
                Day.user_id == user_id,
                Day.date == log_date,
            )
        )
        if day_id is not None:
            await db.execute(
                delete(HabitLog).where(
                    HabitLog.habit_id == habit_id,
                    HabitLog.day_id == day_id,
                )
            )
        await db.commit()
        return

    day_insert = pg_insert(Day).values(
        user_id=user_id,
        date=log_date,
    )
    day_result = await db.execute(
        day_insert.on_conflict_do_nothing(
            index_elements=[Day.user_id, Day.date]
        ).returning(Day.id)
    )
    day_id = day_result.scalar_one_or_none()
    if day_id is None:
        day_id = await db.scalar(
            select(Day.id).where(
                Day.user_id == user_id,
                Day.date == log_date,
            )
        )
    if day_id is None:
        raise RuntimeError("day disappeared while toggling habit")

    await db.execute(
        pg_insert(HabitLog)
        .values(habit_id=habit_id, day_id=day_id)
        .on_conflict_do_nothing(
            index_elements=[HabitLog.day_id, HabitLog.habit_id]
        )
    )
    await db.commit()

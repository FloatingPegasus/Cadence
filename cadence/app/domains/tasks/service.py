from datetime import date, datetime, timezone

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.task import Task
from ...services import embeddings as embedding_service
from ...services.continuity_lock import acquire_continuity_lock


class TaskNotFoundError(LookupError):
    """Raised when a task does not belong to the current user."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "is_completed": bool(task.is_completed),
        "is_abandoned": bool(task.is_abandoned),
        "completed_at": (
            task.completed_at.isoformat() if task.completed_at else None
        ),
    }


def open_task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def _open_as_of(user_id: int, on_or_before: date) -> list:
    return [
        Task.user_id == user_id,
        Task.is_completed.is_(False),
        Task.is_abandoned.is_(False),
        cast(Task.created_at, Date) <= on_or_before,
    ]


async def open_tasks(
    db: AsyncSession,
    user_id: int,
    on_or_before: date,
    *,
    context_id: int | None = None,
    limit: int = 20,
    oldest_first: bool = False,
) -> list[dict]:
    query = select(Task).where(*_open_as_of(user_id, on_or_before))
    if context_id is not None:
        query = (
            query.join(
                Day,
                and_(
                    Day.user_id == Task.user_id,
                    Day.date == cast(Task.created_at, Date),
                ),
            )
            .join(DayContext, DayContext.day_id == Day.id)
            .where(DayContext.context_id == context_id)
        )
    order = (
        (Task.created_at, Task.id)
        if oldest_first
        else (Task.created_at.desc(), Task.id.desc())
    )
    rows = await db.scalars(query.order_by(*order).limit(limit))
    return [open_task_payload(task) for task in rows]


async def count_open_tasks(
    db: AsyncSession, user_id: int, on_or_before: date
) -> int:
    return await db.scalar(
        select(func.count(Task.id)).where(*_open_as_of(user_id, on_or_before))
    )


async def _sync_embedding(db: AsyncSession, user_id: int, task: Task) -> None:
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="tasks",
        source_id=task.id,
        source_date=task.created_at.date(),
        content=task.title,
    )


async def list_tasks(
    db: AsyncSession,
    user_id: int,
    *,
    due_on: date | None = None,
    month: str | None = None,
) -> list[dict]:
    query = select(Task).where(Task.user_id == user_id)
    if due_on is not None:
        query = query.where(Task.due_date == due_on)
    elif month is not None:
        first = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        if first.month == 12:
            next_month = first.replace(year=first.year + 1, month=1)
        else:
            next_month = first.replace(month=first.month + 1)
        query = query.where(
            Task.due_date >= first,
            Task.due_date < next_month,
        )
    rows = await db.scalars(
        query.order_by(Task.is_completed, Task.due_date.nulls_last(), Task.id)
    )
    return [_serialize(task) for task in rows]


async def create_task(
    db: AsyncSession,
    user_id: int,
    *,
    title: str,
    due_date: date | None = None,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    now = _now()
    task = Task(
        user_id=user_id,
        title=title,
        due_date=due_date,
        is_completed=False,
        is_abandoned=False,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    payload = _serialize(task)
    await _sync_embedding(db, user_id, task)
    return payload


async def update_task(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    title: str | None = None,
    due_date: date | None = None,
    is_completed: bool | None = None,
    is_abandoned: bool | None = None,
    due_date_set: bool = False,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    task = await db.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    if task is None:
        raise TaskNotFoundError(task_id)
    if title is not None:
        task.title = title
    if due_date_set:
        task.due_date = due_date
    if is_completed is not None and is_completed != bool(task.is_completed):
        task.is_completed = is_completed
        task.completed_at = _now() if is_completed else None
        if is_completed:
            task.is_abandoned = False
    if is_abandoned is not None and is_abandoned != bool(task.is_abandoned):
        task.is_abandoned = is_abandoned
        if is_abandoned:
            task.is_completed = False
            task.completed_at = None
    task.updated_at = _now()
    await db.commit()
    await db.refresh(task)
    payload = _serialize(task)
    await _sync_embedding(db, user_id, task)
    return payload


async def delete_task(
    db: AsyncSession,
    user_id: int,
    task_id: int,
) -> None:
    await acquire_continuity_lock(db, user_id)
    task = await db.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    if task is None:
        raise TaskNotFoundError(task_id)
    await db.delete(task)
    await db.commit()
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="tasks",
        source_id=task_id,
        content="",
    )

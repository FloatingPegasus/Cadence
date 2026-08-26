from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.user_goal import GOAL_KINDS, UserGoal
from ...services.continuity_lock import acquire_continuity_lock


MAX_GOALS_PER_USER = 24


class GoalNotFoundError(LookupError):
    """Raised when a goal does not belong to the current user."""


def _serialize(goal: UserGoal) -> dict:
    return {
        "id": goal.id,
        "kind": goal.kind,
        "title": goal.title,
        "notes": goal.notes or "",
        "sort_order": goal.sort_order,
        "updated_at": goal.updated_at.isoformat() if goal.updated_at else None,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def list_goals(db: AsyncSession, user_id: int) -> list[dict]:
    rows = await db.scalars(
        select(UserGoal)
        .where(UserGoal.user_id == user_id)
        .order_by(UserGoal.sort_order, UserGoal.id)
    )
    return [_serialize(goal) for goal in rows]


async def create_goal(
    db: AsyncSession,
    user_id: int,
    *,
    kind: str,
    title: str,
    notes: str = "",
) -> dict:
    if kind not in GOAL_KINDS:
        raise ValueError("Unknown goal kind")
    await acquire_continuity_lock(db, user_id)
    count = await db.scalar(
        select(func.count()).select_from(UserGoal).where(UserGoal.user_id == user_id)
    )
    if (count or 0) >= MAX_GOALS_PER_USER:
        raise ValueError("Goal limit reached")
    goal = UserGoal(
        user_id=user_id,
        kind=kind,
        title=title,
        notes=notes.strip(),
        sort_order=count or 0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return _serialize(goal)


async def update_goal(
    db: AsyncSession,
    user_id: int,
    goal_id: int,
    *,
    title: str | None = None,
    notes: str | None = None,
    kind: str | None = None,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    goal = await db.scalar(
        select(UserGoal).where(UserGoal.id == goal_id, UserGoal.user_id == user_id)
    )
    if goal is None:
        raise GoalNotFoundError
    if kind is not None:
        if kind not in GOAL_KINDS:
            raise ValueError("Unknown goal kind")
        goal.kind = kind
    if title is not None:
        goal.title = title
    if notes is not None:
        goal.notes = notes.strip()
    goal.updated_at = _now()
    await db.commit()
    await db.refresh(goal)
    return _serialize(goal)


async def delete_goal(db: AsyncSession, user_id: int, goal_id: int) -> None:
    await acquire_continuity_lock(db, user_id)
    goal = await db.scalar(
        select(UserGoal).where(UserGoal.id == goal_id, UserGoal.user_id == user_id)
    )
    if goal is None:
        raise GoalNotFoundError
    await db.delete(goal)
    await db.commit()

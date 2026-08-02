from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.habits import service as habits_service
from ...domains.discipline_continuity import service as discipline_service
from ...extensions import get_db
from .auth import get_current_user
from ...persistence.models.user import User

router = APIRouter(tags=["habits"])


class HabitToggle(BaseModel):
    habit_id: int
    date: date
    value: Literal["0", "1"]


class HabitWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Habit name cannot be blank")
        return normalized


@router.get("/habits")
async def list_habits(
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await habits_service.list_habits(
        db, user.id, include_archived=include_archived
    )


def _translate_habit_error(error: Exception) -> None:
    if isinstance(error, habits_service.HabitNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found"
        )
    if isinstance(error, habits_service.HabitNameConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active habit already uses that name",
        )
    raise error


@router.post("/habits", status_code=status.HTTP_201_CREATED)
async def create_habit(
    body: HabitWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await habits_service.create_habit(db, user.id, body.name)
    except (
        habits_service.HabitNameConflictError,
        habits_service.HabitNotFoundError,
    ) as error:
        _translate_habit_error(error)


@router.patch("/habits/{habit_id}")
async def rename_habit(
    habit_id: int,
    body: HabitWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await habits_service.rename_habit(
            db, user.id, habit_id, body.name
        )
    except (
        habits_service.HabitNameConflictError,
        habits_service.HabitNotFoundError,
    ) as error:
        _translate_habit_error(error)


@router.delete("/habits/{habit_id}")
async def archive_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await habits_service.archive_habit(db, user.id, habit_id)
    except habits_service.HabitNotFoundError as error:
        _translate_habit_error(error)


@router.get("/habits/month")
async def get_month_data(
    month: str = Query(
        default_factory=lambda: __import__("datetime").date.today().strftime("%Y-%m"),
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await habits_service.get_month_data(db, user.id, month)


@router.get("/habits/{habit_id}/months/{target_month}")
async def get_discipline_month(
    habit_id: int,
    target_month: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await discipline_service.get_discipline_month(
            db,
            user.id,
            habit_id,
            target_month,
        )
    except discipline_service.DisciplineNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discipline not found",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Month must use YYYY-MM format",
        )


@router.post("/habits/toggle")
async def toggle_habit(
    body: HabitToggle,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await habits_service.toggle_habit(
            db, user.id, body.habit_id, body.date, body.value
        )
    except habits_service.HabitNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found"
        )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid habit toggle"
        )
    return {"status": "ok"}

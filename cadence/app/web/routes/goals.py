from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.goals import service as goals_service
from ...extensions import get_db
from ...persistence.models.user import User
from ...persistence.models.user_goal import GOAL_KINDS
from .auth import get_current_user


router = APIRouter(tags=["goals"])


class GoalCreate(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2_000)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        kind = value.strip()
        if kind not in GOAL_KINDS:
            raise ValueError("Unknown goal kind")
        return kind

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Goal title cannot be blank")
        return title


class GoalUpdate(BaseModel):
    kind: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2_000)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str | None) -> str | None:
        if value is None:
            return value
        kind = value.strip()
        if kind not in GOAL_KINDS:
            raise ValueError("Unknown goal kind")
        return kind

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        title = value.strip()
        if not title:
            raise ValueError("Goal title cannot be blank")
        return title


@router.get("/goals")
async def list_goals(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await goals_service.list_goals(db, user.id)


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await goals_service.create_goal(
            db,
            user.id,
            kind=body.kind,
            title=body.title,
            notes=body.notes,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await goals_service.update_goal(
            db,
            user.id,
            goal_id,
            title=body.title,
            notes=body.notes,
            kind=body.kind,
        )
    except goals_service.GoalNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await goals_service.delete_goal(db, user.id, goal_id)
    except goals_service.GoalNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

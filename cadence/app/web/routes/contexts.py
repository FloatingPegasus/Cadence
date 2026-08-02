from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.contexts import service as contexts_service
from ...domains.context_monthly import service as context_monthly_service
from ...extensions import get_db
from ...persistence.models.user import User
from .auth import get_current_user

router = APIRouter(tags=["contexts"])


class ContextWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["project", "learning", "area"] = "area"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Context name cannot be blank")
        return normalized


class DayContextsUpdate(BaseModel):
    context_ids: list[int] = Field(max_length=20)


def _translate_context_error(error: Exception) -> None:
    if isinstance(error, contexts_service.ContextNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context not found",
        )
    if isinstance(error, contexts_service.ContextNameConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active context already uses that name",
        )
    raise error


@router.get("/contexts")
async def list_contexts(
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await contexts_service.list_contexts(
        db,
        user.id,
        include_archived,
    )


@router.post("/contexts", status_code=status.HTTP_201_CREATED)
async def create_context(
    body: ContextWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await contexts_service.create_context(
            db,
            user.id,
            body.name,
            body.kind,
        )
    except contexts_service.ContextNameConflictError as error:
        _translate_context_error(error)


@router.patch("/contexts/{context_id}")
async def update_context(
    context_id: int,
    body: ContextWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await contexts_service.update_context(
            db,
            user.id,
            context_id,
            body.name,
            body.kind,
        )
    except (
        contexts_service.ContextNameConflictError,
        contexts_service.ContextNotFoundError,
    ) as error:
        _translate_context_error(error)


@router.delete("/contexts/{context_id}")
async def archive_context(
    context_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await contexts_service.archive_context(
            db,
            user.id,
            context_id,
        )
    except contexts_service.ContextNotFoundError as error:
        _translate_context_error(error)


@router.get("/contexts/{context_id}/continuity")
async def get_context_continuity(
    context_id: int,
    limit: int = Query(default=12, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await contexts_service.get_continuity(
            db,
            user.id,
            context_id,
            limit,
        )
    except contexts_service.ContextNotFoundError as error:
        _translate_context_error(error)


@router.get("/contexts/{context_id}/months/{target_month}")
async def get_context_month(
    context_id: int,
    target_month: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await context_monthly_service.get_context_month(
            db,
            user.id,
            context_id,
            target_month,
        )
    except context_monthly_service.ContextMonthNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context not found",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Month must use YYYY-MM format",
        )


@router.get("/days/{target_date}/contexts")
async def list_day_contexts(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await contexts_service.list_for_day(db, user.id, target_date)


@router.put("/days/{target_date}/contexts")
async def set_day_contexts(
    target_date: date,
    body: DayContextsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await contexts_service.set_for_day(
            db,
            user.id,
            target_date,
            body.context_ids,
        )
    except contexts_service.ContextNotFoundError as error:
        _translate_context_error(error)

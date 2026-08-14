from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.continuity import service as continuity_service
from ...domains.monthly import service as monthly_service
from ...domains.weekly_reflections import service as reflections_service
from ...domains.patterns import service as patterns_service
from ...extensions import get_db
from ...persistence.models.user import User
from ...services import ai as ai_service
from .auth import get_current_user

router = APIRouter(tags=["continuity"])


@router.get("/continuity/patterns")
async def get_patterns(
    anchor_date: date = Query(default_factory=date.today),
    weeks: int = Query(default=8, ge=4, le=12),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await patterns_service.get_patterns(
        db,
        user.id,
        anchor_date,
        weeks,
    )


class WeeklyReflectionUpdate(BaseModel):
    content: str = Field(max_length=30_000)


class WeeklyReflectionGenerate(BaseModel):
    replace_edited: bool = False


@router.get("/continuity/weeks/{anchor_date}")
async def get_week(
    anchor_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await continuity_service.get_week(db, user.id, anchor_date)


@router.get("/continuity/weeks/{anchor_date}/reflection")
async def get_weekly_reflection(
    anchor_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await reflections_service.get_weekly_reflection(
        db,
        user.id,
        anchor_date,
    )


@router.put("/continuity/weeks/{anchor_date}/reflection")
async def update_weekly_reflection(
    anchor_date: date,
    body: WeeklyReflectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await reflections_service.save_manual_reflection(
        db,
        user.id,
        anchor_date,
        body.content,
    )


@router.post("/continuity/weeks/{anchor_date}/reflection/generate")
async def generate_weekly_reflection(
    anchor_date: date,
    body: WeeklyReflectionGenerate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await reflections_service.generate_weekly_reflection(
            db,
            user.id,
            anchor_date,
            replace_edited=body.replace_edited,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    except ai_service.AIConsentRequiredError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External AI processing is not enabled for this account.",
        )
    except ai_service.AIConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI generation is not available.",
        )
    except ai_service.AIProvidersExhaustedError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider is temporarily unavailable.",
        )


@router.get("/continuity/reflections")
async def list_weekly_reflections(
    limit: int = Query(default=12, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await reflections_service.list_weekly_reflections(
        db,
        user.id,
        limit,
    )


@router.get("/continuity/months/{target_month}")
async def get_month(
    target_month: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await monthly_service.get_month(
            db,
            user.id,
            target_month,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Month must use YYYY-MM format",
        )


@router.get("/continuity/search")
async def search(
    q: str = Query(min_length=2, max_length=200),
    source: Literal[
        "all",
        "notes",
        "conversation",
        "summaries",
        "threads",
        "weekly_reflections",
    ] = "all",
    start_date: date | None = None,
    end_date: date | None = None,
    context_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    search_end = end_date or date.today()
    search_start = start_date or search_end - timedelta(days=364)
    if search_start > search_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must not be after end_date",
        )
    if (search_end - search_start).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Search range cannot exceed 366 days",
        )
    try:
        return await continuity_service.search(
            db,
            user.id,
            q.strip(),
            search_start,
            search_end,
            source,
            limit,
            context_id,
        )
    except continuity_service.ContextFilterNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context not found",
        )

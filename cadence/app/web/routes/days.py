from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.days import service as days_service
from ...domains.summaries import service as summaries_service
from ...domains.carry_forward import service as carry_forward_service
from ...domains.continuity import service as continuity_service
from ...services import ai as ai_service
from ...extensions import get_db
from .auth import get_current_user
from ...persistence.models.user import User

router = APIRouter(tags=["days"])


class DailyNoteUpdate(BaseModel):
    daily_note: str = Field(max_length=20_000)


class CheckinUpdate(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    energy_level: int | None = Field(default=None, ge=1, le=5)
    focus_quality: int | None = Field(default=None, ge=1, le=5)
    emotional_state: str | None = Field(default=None, max_length=100)
    recovery_quality: int | None = Field(default=None, ge=1, le=5)
    reentry_success: int | None = Field(default=None, ge=1, le=5)
    drift_minutes: int | None = Field(default=None, ge=0, le=1440)
    notes: str | None = Field(default=None, max_length=10_000)


class ConversationEntryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class SummaryUpdate(BaseModel):
    content: str = Field(max_length=20_000)


class SummaryGenerate(BaseModel):
    replace_edited: bool = False


class DayStatusUpdate(BaseModel):
    status: Literal["open", "closed"]


class CarryForwardCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2_000)


class CarryForwardStatusUpdate(BaseModel):
    status: Literal["open", "completed", "released"]


@router.get("/days")
async def list_recent_days(
    limit: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.list_recent_days(db, user.id, limit)


@router.get("/days/{target_date}")
async def get_day(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.get_day(db, user.id, target_date)


@router.put("/days/{target_date}")
async def update_day(
    target_date: date,
    body: DailyNoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.update_day(db, user.id, target_date, body.daily_note)


@router.patch("/days/{target_date}/status")
async def update_day_status(
    target_date: date,
    body: DayStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.update_day_status(
        db, user.id, target_date, body.status
    )


@router.get("/days/{target_date}/closure")
async def get_closure_preview(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.get_closure_preview(
        db, user.id, target_date
    )


@router.get("/days/{target_date}/context")
async def get_day_context(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.get_day_context(db, user.id, target_date)


@router.get("/days/{target_date}/reentry")
async def get_day_reentry(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await continuity_service.get_day_reentry(
        db, user.id, target_date
    )


@router.get("/days/{target_date}/checkin")
async def get_checkin(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.get_checkin(db, user.id, target_date)


@router.put("/days/{target_date}/checkin")
async def update_checkin(
    target_date: date,
    body: CheckinUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.update_checkin(
        db, user.id, target_date, body.model_dump(exclude_unset=True)
    )


@router.get("/days/{target_date}/conversation")
async def list_conversation(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.list_conversation(db, user.id, target_date)


@router.post("/days/{target_date}/conversation")
async def add_conversation_entry(
    target_date: date,
    body: ConversationEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.add_conversation_entry(
        db, user.id, target_date, body.content
    )


@router.get("/days/{target_date}/summary")
async def get_summary(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await summaries_service.get_daily_summary(
        db, user.id, target_date
    )


@router.put("/days/{target_date}/summary")
async def update_summary(
    target_date: date,
    body: SummaryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await summaries_service.save_manual_summary(
        db, user.id, target_date, body.content
    )


@router.post("/days/{target_date}/summary/generate")
async def generate_summary(
    target_date: date,
    body: SummaryGenerate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await summaries_service.generate_daily_summary(
            db,
            user.id,
            target_date,
            replace_edited=body.replace_edited,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        )
    except ai_service.AIConsentRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
    except ai_service.AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )
    except ai_service.AIProvidersExhaustedError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
        )


@router.get("/days/{target_date}/carry-forward")
async def list_carry_forward(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await carry_forward_service.list_for_day(
        db, user.id, target_date
    )


@router.post(
    "/days/{target_date}/carry-forward",
    status_code=status.HTTP_201_CREATED,
)
async def create_carry_forward(
    target_date: date,
    body: CarryForwardCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await carry_forward_service.create_item(
        db, user.id, target_date, body.content
    )


@router.patch("/days/{target_date}/carry-forward/{item_id}")
async def update_carry_forward(
    target_date: date,
    item_id: int,
    body: CarryForwardStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await carry_forward_service.update_status(
            db, user.id, item_id, body.status
        )
    except carry_forward_service.CarryForwardNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carry-forward item not found",
        )

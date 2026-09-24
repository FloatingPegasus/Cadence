from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.companion import service as companion_service
from ...domains.days import service as days_service
from ...domains.habits import service as habits_service
from ...domains.summaries import service as summaries_service
from ...domains.continuity import service as continuity_service
from ...config import settings
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


class LogContent(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("Log cannot be blank")
        return content


class LogCreate(LogContent):
    hour: int | None = Field(default=None, ge=0, le=23)
    reply: bool = False


class SummaryUpdate(BaseModel):
    content: str = Field(max_length=20_000)


class SummaryGenerate(BaseModel):
    replace_edited: bool = False


class DayStatusUpdate(BaseModel):
    status: Literal["open", "closed"]


@router.get("/days")
async def list_recent_days(
    limit: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.list_recent_days(db, user.id, limit)


@router.get("/days/{target_date}/habits")
async def get_day_habits(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await habits_service.get_day_habits(db, user.id, target_date)


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


@router.post("/days/{target_date}/begin")
async def begin_day(
    target_date: date,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.auto_close:
        return {"closed": []}
    user_id = user.id
    summarize = (
        settings.ai_enabled
        and user.ai_processing_consent
        and not user.is_guest
    )
    closed = await days_service.close_past_days(db, user_id, target_date)
    recent = [day for day in closed if day >= target_date - timedelta(days=7)]
    if summarize and recent:
        background_tasks.add_task(
            summaries_service.summarize_closed_days, db, user_id, recent
        )
    return {"closed": [day.isoformat() for day in closed]}


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


@router.get("/days/{target_date}/logs")
async def list_logs(
    target_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await days_service.list_logs(db, user.id, target_date)


@router.post("/days/{target_date}/logs", status_code=status.HTTP_201_CREATED)
async def add_log(
    target_date: date,
    body: LogCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await companion_service.add_log(
        db, user, target_date, body.content, body.hour, reply=body.reply
    )


@router.patch("/days/{target_date}/logs/{entry_id}")
async def update_log(
    target_date: date,
    entry_id: int,
    body: LogContent,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await days_service.update_log(
        db, user.id, target_date, entry_id, body.content
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Log not found"
        )
    return entry


@router.delete(
    "/days/{target_date}/logs/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_log(
    target_date: date,
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not await days_service.delete_log(db, user.id, target_date, entry_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Log not found"
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

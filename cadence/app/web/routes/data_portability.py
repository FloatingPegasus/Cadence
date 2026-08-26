from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.data_portability import service
from ...extensions import get_db
from ...persistence.models.user import User
from ...services import embeddings as embedding_service
from .auth import get_current_user

router = APIRouter(tags=["data portability"])


class AIPreferencesUpdate(BaseModel):
    processing_consent: bool
    redaction_enabled: bool


def _ai_preferences(user: User) -> dict:
    return {
        "processing_consent": user.ai_processing_consent,
        "redaction_enabled": user.ai_redaction_enabled,
        "provider": "NVIDIA Build API",
        "external_processing": True,
        "redaction_scope": (
            "Common email addresses and phone-like numbers are replaced "
            "before text is sent. Local source records remain unchanged."
        ),
    }


@router.get("/account/ai-preferences")
async def get_ai_preferences(
    user: User = Depends(get_current_user),
):
    return _ai_preferences(user)


@router.put("/account/ai-preferences")
async def update_ai_preferences(
    body: AIPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    redaction_changed = user.ai_redaction_enabled != body.redaction_enabled
    user.ai_processing_consent = body.processing_consent
    user.ai_redaction_enabled = body.redaction_enabled
    if not body.processing_consent or redaction_changed:
        await embedding_service.purge_user_embeddings(db, user.id)
    await db.commit()
    await db.refresh(user)
    return _ai_preferences(user)


@router.get("/account/export")
async def export_account(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = await service.export_user_data(db, user)
    filename = f"cadence-export-{date.today().isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

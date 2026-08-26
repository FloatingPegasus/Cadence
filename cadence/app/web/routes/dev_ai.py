from fastapi import APIRouter, Depends, HTTPException, status
import logging
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...extensions import get_db
from ...persistence.models.user import User
from ...services import ai as ai_service
from .auth import get_current_user, is_developer


router = APIRouter(tags=["dev-ai"])
logger = logging.getLogger("cadence.dev_ai")


async def require_developer(
    user: User = Depends(get_current_user),
) -> User:
    if not is_developer(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user


class ModelTestRequest(BaseModel):
    model_ids: list[str] = Field(default_factory=list, max_length=200)
    test_all: bool = False


@router.get("/dev/ai/models")
async def models(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    _developer: User = Depends(require_developer),
):
    if settings.ai_api_key:
        try:
            result = await ai_service.sync_nvidia_catalog(
                db, force=refresh
            )
            return {
                "configured": True,
                "ranking_version": ai_service.RANKING_VERSION,
                **result,
            }
        except Exception:
            logger.exception("AI catalog refresh failed")
            await db.rollback()
            return {
                "configured": True,
                "refreshed": False,
                "ranking_version": ai_service.RANKING_VERSION,
                "sync_error": "AI model catalog refresh failed",
                "models": await ai_service.list_models(db),
            }
    return {
        "configured": False,
        "refreshed": False,
        "ranking_version": ai_service.RANKING_VERSION,
        "models": await ai_service.list_models(db),
    }


@router.post("/dev/ai/models/test")
async def test_models(
    body: ModelTestRequest,
    db: AsyncSession = Depends(get_db),
    _developer: User = Depends(require_developer),
):
    if not settings.ai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CADENCE_AI_API_KEY is not configured",
        )
    available = await ai_service.list_models(db)
    available_ids = [model["model_id"] for model in available]
    selected = available_ids if body.test_all else body.model_ids
    if not selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide model_ids or set test_all=true",
        )
    unknown = sorted(set(selected) - set(available_ids))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"unknown_models": unknown},
        )
    results = []
    for model_id in selected:
        results.append(await ai_service.probe_model(db, model_id))
    return {"tested": len(results), "models": results}


@router.get("/dev/ai/fallback/{task}")
async def get_fallback_chain(
    task: str,
    db: AsyncSession = Depends(get_db),
    _developer: User = Depends(require_developer),
):
    if task not in {"summary", "context", "extraction", "general"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown AI task"
        )
    return {
        "task": task,
        "models": await ai_service.fallback_chain(db, task),
        "ranking_version": ai_service.RANKING_VERSION,
    }

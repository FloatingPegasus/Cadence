from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from time import perf_counter

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..persistence.models.ai_model import AIModel
from ..persistence.models.user import User


RANKING_VERSION = "2026-07-23"

CURATED_STRENGTH = {
    "nvidia/nemotron-3-ultra-550b-a55b": 100,
    "z-ai/glm-5.2": 98,
    "moonshotai/kimi-k2.6": 96,
    "minimaxai/minimax-m3": 94,
    "thinkingmachines/inkling": 93,
    "qwen/qwen3.5-397b-a17b": 92,
    "mistralai/mistral-medium-3.5-128b": 90,
    "mistralai/mistral-small-4-119b-2603": 88,
    "stepfun-ai/step-3.7-flash": 86,
    "google/gemma-4-31b-it": 84,
    "qwen/qwen3-next-80b-a3b-instruct": 82,
}

TASK_PREFERENCE = {
    "summary": [
        "mistralai/mistral-medium-3.5-128b",
        "z-ai/glm-5.2",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ],
    "context": [
        "nvidia/nemotron-3-ultra-550b-a55b",
        "z-ai/glm-5.2",
        "moonshotai/kimi-k2.6",
    ],
    "extraction": [
        "qwen/qwen3-next-80b-a3b-instruct",
        "google/gemma-4-31b-it",
        "mistralai/mistral-small-4-119b-2603",
    ],
}

NON_CHAT_MARKERS = (
    "embed",
    "rerank",
    "guard",
    "safety",
    "flux",
    "image",
    "video",
    "ocr",
    "audio",
    "speech",
    "cosmos",
)


class AIConfigurationError(RuntimeError):
    pass


class AIProvidersExhaustedError(RuntimeError):
    pass


class AIConsentRequiredError(RuntimeError):
    pass


EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)"
)


def redact_sensitive_text(value: str) -> str:
    redacted = EMAIL_PATTERN.sub("[redacted email]", value)
    return PHONE_PATTERN.sub(
        lambda match: (
            "[redacted phone]"
            if len(re.sub(r"\D", "", match.group(0))) >= 9
            else match.group(0)
        ),
        redacted,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def strength_for(model_id: str) -> int:
    normalized = model_id.lower()
    if normalized in CURATED_STRENGTH:
        return CURATED_STRENGTH[normalized]
    if "ultra" in normalized or "flagship" in normalized:
        return 70
    if "large" in normalized or "reason" in normalized:
        return 60
    if "medium" in normalized:
        return 50
    return 0


def is_chat_candidate(model_id: str) -> bool:
    normalized = model_id.lower()
    return not any(marker in normalized for marker in NON_CHAT_MARKERS)


def _headers() -> dict[str, str]:
    if not settings.ai_api_key:
        raise AIConfigurationError("CADENCE_AI_API_KEY is not configured")
    return {"Authorization": f"Bearer {settings.ai_api_key}"}


async def sync_nvidia_catalog(
    db: AsyncSession,
    *,
    force: bool = False,
    client: httpx.AsyncClient | None = None,
) -> dict:
    latest_seen = await db.scalar(
        select(AIModel.last_seen_at)
        .where(AIModel.provider == "nvidia")
        .order_by(AIModel.last_seen_at.desc())
        .limit(1)
    )
    refresh_after = timedelta(minutes=settings.ai_catalog_refresh_minutes)
    if not force and latest_seen and utcnow() - latest_seen < refresh_after:
        models = await list_models(db)
        return {"refreshed": False, "models": models}

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.ai_request_timeout_seconds
        )
    try:
        response = await client.get(
            f"{settings.ai_base_url.rstrip('/')}/models", headers=_headers()
        )
        response.raise_for_status()
        model_ids = sorted(
            {
                item["id"]
                for item in response.json().get("data", [])
                if item.get("id") and is_chat_candidate(item["id"])
            }
        )
        now = utcnow()
        existing_result = await db.execute(
            select(AIModel).where(AIModel.provider == "nvidia")
        )
        existing = {
            model.model_id: model
            for model in existing_result.scalars().all()
        }
        for model_id, model in existing.items():
            if model_id not in model_ids:
                model.health_status = "missing"
        for model_id in model_ids:
            model = existing.get(model_id)
            if model is None:
                model = AIModel(
                    provider="nvidia",
                    model_id=model_id,
                    ranking_version=RANKING_VERSION,
                )
                db.add(model)
            model.strength_score = strength_for(model_id)
            model.ranking_version = RANKING_VERSION
            model.last_seen_at = now
            if model.health_status == "missing":
                model.health_status = "untested"
        await db.commit()
        return {"refreshed": True, "models": await list_models(db)}
    finally:
        if owns_client:
            await client.aclose()


async def list_models(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(AIModel)
        .where(AIModel.provider == "nvidia")
        .order_by(AIModel.strength_score.desc(), AIModel.model_id)
    )
    return [serialize_model(model) for model in result.scalars().all()]


def serialize_model(model: AIModel) -> dict:
    return {
        "id": model.id,
        "provider": model.provider,
        "model_id": model.model_id,
        "strength_score": model.strength_score,
        "ranking_version": model.ranking_version,
        "enabled": model.enabled,
        "health_status": model.health_status,
        "latency_ms": model.latency_ms,
        "last_error": model.last_error,
        "last_seen_at": model.last_seen_at.isoformat(),
        "last_tested_at": (
            model.last_tested_at.isoformat() if model.last_tested_at else None
        ),
    }


async def probe_model(
    db: AsyncSession,
    model_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    result = await db.execute(
        select(AIModel).where(
            AIModel.provider == "nvidia", AIModel.model_id == model_id
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise LookupError(model_id)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.ai_request_timeout_seconds
        )
    started = perf_counter()
    try:
        response = await client.post(
            f"{settings.ai_base_url.rstrip('/')}/chat/completions",
            headers=_headers(),
            json={
                "model": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": "Reply with exactly: CADENCE_OK",
                    }
                ],
                "temperature": 0,
                "max_tokens": 16,
            },
        )
        response.raise_for_status()
        model.health_status = "healthy"
        model.last_error = None
    except Exception as error:
        model.health_status = "unhealthy"
        model.last_error = str(error)[:1000]
    finally:
        model.latency_ms = round((perf_counter() - started) * 1000, 2)
        model.last_tested_at = utcnow()
        await db.commit()
        if owns_client:
            await client.aclose()
    return serialize_model(model)


async def fallback_chain(db: AsyncSession, task: str) -> list[str]:
    result = await db.execute(
        select(AIModel).where(
            AIModel.provider == "nvidia",
            AIModel.enabled.is_(True),
            AIModel.health_status.not_in(["unhealthy", "missing"]),
        )
    )
    models = list(result.scalars().all())
    preferred = TASK_PREFERENCE.get(task, [])
    preferred_order = {model_id: index for index, model_id in enumerate(preferred)}
    models.sort(
        key=lambda model: (
            model.health_status == "rate_limited",
            preferred_order.get(model.model_id, len(preferred)),
            -model.strength_score,
            model.model_id,
        )
    )
    return [model.model_id for model in models]


async def chat_with_fallback(
    db: AsyncSession,
    *,
    task: str,
    messages: list[dict[str, str]],
    max_tokens: int = 800,
    temperature: float = 0.2,
    client: httpx.AsyncClient | None = None,
    user_id: int | None = None,
) -> dict:
    if not settings.ai_enabled:
        raise AIConfigurationError("Cadence AI is disabled")
    redaction_applied = False
    outbound_messages = messages
    if user_id is not None:
        user = await db.get(User, user_id)
        if user is None or not user.ai_processing_consent:
            raise AIConsentRequiredError(
                "External AI processing is off. Enable it in Settings "
                "before generating."
            )
        if user.ai_redaction_enabled:
            outbound_messages = [
                {
                    **message,
                    "content": redact_sensitive_text(message["content"]),
                }
                for message in messages
            ]
            redaction_applied = True
    chain = await fallback_chain(db, task)
    if not chain:
        await sync_nvidia_catalog(db)
        chain = await fallback_chain(db, task)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.ai_request_timeout_seconds
        )
    failures: list[str] = []
    try:
        for model_id in chain:
            started = perf_counter()
            result = await db.execute(
                select(AIModel).where(
                    AIModel.provider == "nvidia",
                    AIModel.model_id == model_id,
                )
            )
            model = result.scalar_one()
            try:
                response = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                    headers=_headers(),
                    json={
                        "model": model_id,
                        "messages": outbound_messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                model.health_status = "healthy"
                model.last_error = None
                model.latency_ms = round(
                    (perf_counter() - started) * 1000, 2
                )
                model.last_tested_at = utcnow()
                await db.commit()
                return {
                    "provider": "nvidia",
                    "model": model_id,
                    "content": payload["choices"][0]["message"]["content"],
                    "usage": payload.get("usage"),
                    "attempted_models": [*failures, model_id],
                    "redaction_applied": redaction_applied,
                }
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as error:
                status_code = (
                    error.response.status_code
                    if isinstance(error, httpx.HTTPStatusError)
                    else None
                )
                model.health_status = (
                    "rate_limited" if status_code == 429 else "unhealthy"
                )
                model.last_error = str(error)[:1000]
                model.last_tested_at = utcnow()
                await db.commit()
                failures.append(model_id)
        raise AIProvidersExhaustedError(
            f"All configured models failed: {', '.join(failures)}"
        )
    finally:
        if owns_client:
            await client.aclose()

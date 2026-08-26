from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
from time import perf_counter

import httpx
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from ..persistence.models.ai_model import AIModel
from ..persistence.models.user import User


logger = logging.getLogger("cadence.ai")


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


def _safe_provider_error(error: Exception) -> str:
    """Return a bounded diagnostic that cannot include provider response data."""

    if isinstance(error, httpx.HTTPStatusError):
        return f"provider returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "provider request timed out"
    if isinstance(error, httpx.RequestError):
        return "provider request failed"
    if isinstance(error, (KeyError, IndexError, TypeError, ValueError)):
        return "provider returned an invalid response"
    return "provider request failed"


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


def _chat_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("provider returned an invalid response")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("provider returned an invalid response")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider returned an invalid response")
    return content


async def sync_nvidia_catalog(
    db: AsyncSession | AsyncConnection,
    *,
    force: bool = False,
    client: httpx.AsyncClient | None = None,
) -> dict:
    if not await release_read_transaction(db):
        raise AIConfigurationError(
            "AI provider calls require a caller session without pending work"
        )
    engine, owns_engine = _caller_async_engine(db)
    owns_client = client is None
    try:
        latest_seen = await _latest_nvidia_seen_from_engine(engine)
        refresh_after = timedelta(minutes=settings.ai_catalog_refresh_minutes)
        if not force and latest_seen and utcnow() - latest_seen < refresh_after:
            session_factory = _catalog_session_factory(engine)
            async with session_factory() as catalog_db:
                models = await list_models(catalog_db)
            return {"refreshed": False, "models": models}

        if client is None:
            client = httpx.AsyncClient(
                timeout=settings.ai_request_timeout_seconds
            )
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
        session_factory = _catalog_session_factory(engine)
        async with session_factory() as catalog_db:
            missing_filter = [AIModel.provider == "nvidia"]
            if model_ids:
                missing_filter.append(~AIModel.model_id.in_(model_ids))
            await catalog_db.execute(
                update(AIModel)
                .where(*missing_filter)
                .values(health_status="missing")
            )
            if model_ids:
                catalog_rows = [
                    {
                        "provider": "nvidia",
                        "model_id": model_id,
                        "strength_score": strength_for(model_id),
                        "ranking_version": RANKING_VERSION,
                        "enabled": True,
                        "health_status": "untested",
                        "last_seen_at": now,
                    }
                    for model_id in model_ids
                ]
                statement = pg_insert(AIModel).values(catalog_rows)
                excluded = statement.excluded
                await catalog_db.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            AIModel.provider,
                            AIModel.model_id,
                        ],
                        set_={
                            "strength_score": excluded.strength_score,
                            "ranking_version": excluded.ranking_version,
                            "last_seen_at": excluded.last_seen_at,
                            "health_status": case(
                                (
                                    AIModel.health_status == "missing",
                                    "untested",
                                ),
                                else_=AIModel.health_status,
                            ),
                        },
                    )
                )
            await catalog_db.commit()
            models = await list_models(catalog_db)
        return {"refreshed": True, "models": models}
    finally:
        try:
            await _close_owned_client(client, owns_client)
        finally:
            await _dispose_owned_engine(engine, owns_engine)


def _caller_async_engine(
    caller: AsyncSession | AsyncConnection,
) -> tuple[AsyncEngine, bool]:
    """Resolve the caller's engine without borrowing its transaction."""

    if isinstance(caller, AsyncConnection):
        return caller.engine, False

    bind = getattr(caller, "bind", None)
    if isinstance(bind, AsyncEngine):
        return bind, False
    bound_engine = getattr(bind, "engine", None)
    if isinstance(bound_engine, AsyncEngine):
        return bound_engine, False
    if isinstance(bind, AsyncConnection):
        return bind.engine, False

    sync_session = getattr(caller, "sync_session", None)
    sync_bind = getattr(sync_session, "bind", None)
    if sync_bind is None:
        try:
            sync_bind = caller.get_bind()
        except Exception:
            sync_bind = None
    async_engine = getattr(sync_bind, "_async_engine", None)
    if isinstance(async_engine, AsyncEngine):
        return async_engine, False

    url = getattr(sync_bind, "url", None) or getattr(bind, "url", None)
    if url is None:
        raise RuntimeError("AI catalog session has no usable database bind")
    return (
        create_async_engine(url, pool_pre_ping=True),
        True,
    )


def _catalog_session_factory(engine: AsyncEngine):
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def release_read_transaction(
    db: AsyncSession | AsyncConnection,
) -> bool:
    """Release a clean caller transaction without committing its work."""

    if isinstance(db, AsyncSession):
        if not db.in_transaction():
            return True
        sync_session = db.sync_session
        transaction = getattr(sync_session, "_transaction", None)
        has_flushed_work = any(
            bool(getattr(transaction, attribute, ()))
            for attribute in ("_new", "_dirty", "_deleted")
        )
        if db.new or db.dirty or db.deleted or has_flushed_work:
            return False
        if sync_session.expire_on_commit:
            return False
        await db.commit()
        return True
    if isinstance(db, AsyncConnection):
        return False
    return True


async def _close_owned_client(
    client: httpx.AsyncClient | None,
    owns_client: bool,
) -> None:
    if not owns_client or client is None:
        return
    try:
        await client.aclose()
    except Exception:
        logger.warning("AI provider client cleanup failed")


async def _dispose_owned_engine(
    engine: AsyncEngine,
    owns_engine: bool,
) -> None:
    if not owns_engine:
        return
    try:
        await engine.dispose()
    except Exception:
        logger.warning("AI database engine cleanup failed")


async def _rollback_quietly(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        logger.warning("AI database rollback failed")


async def _model_snapshot(
    engine: AsyncEngine,
    model_id: str,
) -> dict | None:
    session_factory = _catalog_session_factory(engine)
    async with session_factory() as model_db:
        result = await model_db.execute(
            select(AIModel).where(
                AIModel.provider == "nvidia",
                AIModel.model_id == model_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            await _rollback_quietly(model_db)
            return None
        snapshot = serialize_model(model)
        await _rollback_quietly(model_db)
        return snapshot


async def _user_ai_snapshot(
    engine: AsyncEngine,
    user_id: int,
) -> tuple[bool, bool] | None:
    session_factory = _catalog_session_factory(engine)
    async with session_factory() as user_db:
        user = await user_db.get(User, user_id)
        snapshot = (
            None
            if user is None
            else (bool(user.ai_processing_consent), bool(user.ai_redaction_enabled))
        )
        await _rollback_quietly(user_db)
        return snapshot


async def _fallback_chain_from_engine(
    engine: AsyncEngine,
    task: str,
) -> list[str]:
    session_factory = _catalog_session_factory(engine)
    async with session_factory() as model_db:
        chain = await fallback_chain(model_db, task)
        await _rollback_quietly(model_db)
        return chain


async def _record_model_state(
    engine: AsyncEngine,
    model_id: str,
    *,
    health_status: str,
    last_error: str | None,
    latency_ms: float,
    tested_at: datetime,
) -> None:
    model_db: AsyncSession | None = None
    try:
        session_factory = _catalog_session_factory(engine)
        async with session_factory() as session:
            model_db = session
            await model_db.execute(
                update(AIModel)
                .where(
                    AIModel.provider == "nvidia",
                    AIModel.model_id == model_id,
                )
                .values(
                    health_status=health_status,
                    last_error=last_error,
                    latency_ms=latency_ms,
                    last_tested_at=tested_at,
                )
            )
            await model_db.commit()
    except Exception:
        if model_db is not None:
            await _rollback_quietly(model_db)
        logger.warning("AI model health write failed model=%s", model_id)


async def _latest_nvidia_seen_from_engine(
    engine: AsyncEngine,
) -> datetime | None:
    session_factory = _catalog_session_factory(engine)
    async with session_factory() as freshness_db:
        return await freshness_db.scalar(
            select(AIModel.last_seen_at)
            .where(AIModel.provider == "nvidia")
            .order_by(AIModel.last_seen_at.desc())
            .limit(1)
        )


async def _latest_nvidia_seen(
    caller: AsyncSession | AsyncConnection,
) -> datetime | None:
    """Read catalog freshness without holding the caller during HTTP."""

    engine, owns_engine = _caller_async_engine(caller)
    try:
        return await _latest_nvidia_seen_from_engine(engine)
    finally:
        await _dispose_owned_engine(engine, owns_engine)


async def list_models(db: AsyncSession | AsyncConnection) -> list[dict]:
    if isinstance(db, AsyncConnection):
        async with AsyncSession(bind=db, expire_on_commit=False) as session:
            return await list_models(session)
    result = await db.execute(
        select(AIModel)
        .where(AIModel.provider == "nvidia")
        .order_by(AIModel.strength_score.desc(), AIModel.model_id)
    )
    return [serialize_model(model) for model in result.scalars().all()]


def serialize_model(model: AIModel) -> dict:
    safe_last_error = model.last_error
    if safe_last_error and not (
        safe_last_error in {
            "provider request failed",
            "provider request timed out",
            "provider returned an invalid response",
        }
        or re.fullmatch(r"provider returned HTTP \d{3}", safe_last_error)
    ):
        safe_last_error = "provider request failed"
    return {
        "id": model.id,
        "provider": model.provider,
        "model_id": model.model_id,
        "strength_score": model.strength_score,
        "ranking_version": model.ranking_version,
        "enabled": model.enabled,
        "health_status": model.health_status,
        "latency_ms": model.latency_ms,
        # Older rows may contain diagnostics written before errors were
        # sanitized. Never return those values through the developer API.
        "last_error": safe_last_error,
        "last_seen_at": (
            model.last_seen_at.isoformat() if model.last_seen_at else None
        ),
        "last_tested_at": (
            model.last_tested_at.isoformat() if model.last_tested_at else None
        ),
    }


async def probe_model(
    db: AsyncSession | AsyncConnection,
    model_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    if not await release_read_transaction(db):
        raise AIConfigurationError(
            "AI provider calls require a caller session without pending work"
        )
    engine, owns_engine = _caller_async_engine(db)
    owns_client = client is None
    response_state: dict | None = None
    try:
        response_state = await _model_snapshot(engine, model_id)
        if response_state is None:
            raise LookupError(model_id)
        started = perf_counter()
        health_status = "healthy"
        last_error = None
        try:
            if client is None:
                client = httpx.AsyncClient(
                    timeout=settings.ai_request_timeout_seconds
                )
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
            _chat_content(response.json())
        except Exception as error:
            health_status = "unhealthy"
            last_error = _safe_provider_error(error)
            logger.warning(
                "AI model probe failed model=%s reason=%s",
                model_id,
                last_error,
            )
        latency_ms = round((perf_counter() - started) * 1000, 2)
        tested_at = utcnow()
        await _record_model_state(
            engine,
            model_id,
            health_status=health_status,
            last_error=last_error,
            latency_ms=latency_ms,
            tested_at=tested_at,
        )
        response_state.update(
            {
                "health_status": health_status,
                "last_error": last_error,
                "latency_ms": latency_ms,
                "last_tested_at": tested_at.isoformat(),
            }
        )
        return response_state
    finally:
        try:
            await _close_owned_client(client, owns_client)
        finally:
            await _dispose_owned_engine(engine, owns_engine)


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
    db: AsyncSession | AsyncConnection,
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
    if not await release_read_transaction(db):
        raise AIConfigurationError(
            "AI provider calls require a caller session without pending work"
        )
    engine, owns_engine = _caller_async_engine(db)
    owns_client = client is None
    redaction_applied = False
    outbound_messages = messages
    try:
        if user_id is not None:
            consent_snapshot = await _user_ai_snapshot(engine, user_id)
            if consent_snapshot is None or not consent_snapshot[0]:
                raise AIConsentRequiredError(
                    "External AI processing is off. Enable it in Settings "
                    "before generating."
                )
            if consent_snapshot[1]:
                outbound_messages = [
                    {
                        **message,
                        "content": redact_sensitive_text(message["content"]),
                    }
                    for message in messages
                ]
                redaction_applied = True
        chain = await _fallback_chain_from_engine(engine, task)
        if not chain:
            if client is None:
                client = httpx.AsyncClient(
                    timeout=settings.ai_request_timeout_seconds
                )
            await sync_nvidia_catalog(db, client=client)
            chain = await _fallback_chain_from_engine(engine, task)
        if client is None:
            client = httpx.AsyncClient(
                timeout=settings.ai_request_timeout_seconds
            )
        failures: list[str] = []
        for model_id in chain:
            started = perf_counter()
            model_state = await _model_snapshot(engine, model_id)
            if model_state is None:
                failures.append(model_id)
                continue
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
                content = _chat_content(payload)
                latency_ms = round((perf_counter() - started) * 1000, 2)
                tested_at = utcnow()
                await _record_model_state(
                    engine,
                    model_id,
                    health_status="healthy",
                    last_error=None,
                    latency_ms=latency_ms,
                    tested_at=tested_at,
                )
                return {
                    "provider": "nvidia",
                    "model": model_id,
                    "content": content,
                    "usage": payload.get("usage"),
                    "attempted_models": [*failures, model_id],
                    "redaction_applied": redaction_applied,
                }
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ) as error:
                status_code = (
                    error.response.status_code
                    if isinstance(error, httpx.HTTPStatusError)
                    else None
                )
                health_status = (
                    "rate_limited" if status_code == 429 else "unhealthy"
                )
                last_error = _safe_provider_error(error)
                logger.warning(
                    "AI model request failed model=%s reason=%s",
                    model_id,
                    last_error,
                )
                await _record_model_state(
                    engine,
                    model_id,
                    health_status=(
                        "rate_limited" if status_code == 429 else "unhealthy"
                    ),
                    last_error=last_error,
                    latency_ms=round((perf_counter() - started) * 1000, 2),
                    tested_at=utcnow(),
                )
                failures.append(model_id)
        raise AIProvidersExhaustedError("AI providers are temporarily unavailable")
    finally:
        try:
            await _close_owned_client(client, owns_client)
        finally:
            await _dispose_owned_engine(engine, owns_engine)

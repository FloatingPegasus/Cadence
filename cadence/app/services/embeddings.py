"""Consent-gated NVIDIA embeddings for continuity records.

Embedding writes are deliberately best-effort.  A source record is committed
by its owning service before this module is called, and a provider failure
leaves the source searchable through the lexical path.
"""

from __future__ import annotations

from hashlib import sha256
import logging
from math import isfinite
from typing import Literal

import httpx
from sqlalchemy import (
    and_,
    delete,
    func,
    literal,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from ..config import settings
from ..persistence.models.carry_forward_item import CarryForwardItem
from ..persistence.models.continuity_embedding import (
    CONTINUITY_EMBEDDING_DIMENSION,
    ContinuityEmbedding,
)
from ..persistence.models.conversation_entry import ConversationEntry
from ..persistence.models.day import Day
from ..persistence.models.summary_artifact import SummaryArtifact
from ..persistence.models.user import User
from ..persistence.models.weekly_reflection import WeeklyReflection
from . import ai as ai_service


logger = logging.getLogger("cadence.embeddings")

EMBEDDING_INPUT_TYPE = Literal["passage", "query"]
MAX_BACKFILL_BATCH = 100
BACKFILL_SOURCE_SCAN_LIMIT = MAX_BACKFILL_BATCH * 4
EMBEDDING_RETRY_LEASE_SECONDS = 300
EMBEDDING_MIN_NORM = 1e-6


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider returns an unusable response."""


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _normalized_content(content: str | None) -> str:
    return (content or "").strip()


def _needs_backfill(content: str | None, existing) -> bool:
    normalized = _normalized_content(content)
    if existing is None:
        return bool(normalized)
    if not normalized:
        return True
    return not (
        existing.is_current
        and existing.embedding_model == settings.embedding_model
        and existing.content == normalized
        and existing.content_hash == _content_hash(normalized)
    )


def _sql_needs_backfill(source_content):
    normalized_source = func.trim(func.coalesce(source_content, ""))
    normalized_embedding = func.trim(
        func.coalesce(ContinuityEmbedding.content, "")
    )
    return or_(
        ContinuityEmbedding.id.is_(None),
        ContinuityEmbedding.is_current.is_(False),
        ContinuityEmbedding.embedding_model != settings.embedding_model,
        normalized_source == "",
        normalized_embedding != normalized_source,
    )


def _sql_hash_check(source_content):
    normalized_source = func.trim(func.coalesce(source_content, ""))
    return and_(
        ContinuityEmbedding.id.is_not(None),
        ContinuityEmbedding.is_current.is_(True),
        ContinuityEmbedding.embedding_model == settings.embedding_model,
        func.trim(func.coalesce(ContinuityEmbedding.content, ""))
        == normalized_source,
    )


def _prepared_text(content: str, *, redaction_enabled: bool) -> str:
    prepared = content.strip()
    if redaction_enabled:
        prepared = ai_service.redact_sensitive_text(prepared)
    return prepared[: settings.embedding_input_max_chars]


def _validate_vector(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)):
        raise EmbeddingProviderError("embedding response did not contain a vector")
    if len(value) != CONTINUITY_EMBEDDING_DIMENSION:
        raise EmbeddingProviderError("embedding response had the wrong dimensions")
    vector: list[float] = []
    norm_squared = 0.0
    for item in value:
        if isinstance(item, bool):
            raise EmbeddingProviderError(
                "embedding response contained a non-finite value"
            )
        try:
            number = float(item)
        except (TypeError, ValueError) as error:
            raise EmbeddingProviderError(
                "embedding response contained a non-numeric value"
            ) from error
        if not isfinite(number):
            raise EmbeddingProviderError(
                "embedding response contained a non-finite value"
            )
        vector.append(number)
        norm_squared += number * number
    if not isfinite(norm_squared):
        raise EmbeddingProviderError("embedding response had an invalid norm")
    if norm_squared <= EMBEDDING_MIN_NORM**2:
        raise EmbeddingProviderError("embedding response had a near-zero norm")
    return vector


async def embed_text(
    content: str,
    *,
    input_type: EMBEDDING_INPUT_TYPE,
    redaction_enabled: bool,
    client: httpx.AsyncClient | None = None,
) -> list[float]:
    """Return a validated NVIDIA embedding for a bounded, consented input."""

    if input_type not in {"passage", "query"}:
        raise ValueError("embedding input type must be passage or query")
    prepared = _prepared_text(content, redaction_enabled=redaction_enabled)
    if not prepared:
        raise EmbeddingProviderError("cannot embed empty content")
    if input_type == "query" and len(prepared) < 2:
        raise EmbeddingProviderError(
            "embedding query must contain at least two characters"
        )
    if not settings.ai_enabled or not settings.embedding_enabled:
        raise ai_service.AIConfigurationError(
            "semantic embeddings are not enabled"
        )

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.embedding_request_timeout_seconds
        )
    try:
        response = await client.post(
            f"{settings.ai_base_url.rstrip('/')}/embeddings",
            headers=ai_service._headers(),
            json={
                "input": prepared,
                "input_type": input_type,
                "model": settings.embedding_model,
                "encoding_format": "float",
                "truncate": "END",
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            raise EmbeddingProviderError("embedding response did not contain data")
        first = data[0]
        vector = first.get("embedding") if isinstance(first, dict) else None
        return _validate_vector(vector)
    except ai_service.AIConfigurationError:
        raise
    except EmbeddingProviderError:
        raise
    except Exception as error:
        raise EmbeddingProviderError(ai_service._safe_provider_error(error)) from error
    finally:
        if owns_client:
            await client.aclose()


async def purge_user_embeddings(db: AsyncSession, user_id: int) -> None:
    """Delete every derived embedding owned by a user."""

    await db.execute(
        delete(ContinuityEmbedding).where(
            ContinuityEmbedding.user_id == user_id
        )
    )


def _source_current_exists(
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
):
    """Build an ownership/content predicate for an atomic activation CAS."""

    if source_type == "notes":
        return select(Day.id).where(
            Day.id == source_id,
            Day.user_id == user_id,
            func.trim(func.coalesce(Day.daily_note, "")) == content,
        ).exists()
    if source_type == "conversation":
        return select(ConversationEntry.id).join(
            Day, Day.id == ConversationEntry.day_id
        ).where(
            ConversationEntry.id == source_id,
            Day.user_id == user_id,
            func.trim(ConversationEntry.content) == content,
        ).exists()
    if source_type == "summaries":
        return select(SummaryArtifact.id).join(
            Day, Day.id == SummaryArtifact.day_id
        ).where(
            SummaryArtifact.id == source_id,
            Day.user_id == user_id,
            func.trim(SummaryArtifact.content) == content,
        ).exists()
    if source_type == "threads":
        return select(CarryForwardItem.id).join(
            Day, Day.id == CarryForwardItem.origin_day_id
        ).where(
            CarryForwardItem.id == source_id,
            Day.user_id == user_id,
            func.trim(CarryForwardItem.content) == content,
        ).exists()
    if source_type == "weekly_reflections":
        return select(WeeklyReflection.id).where(
            WeeklyReflection.id == source_id,
            WeeklyReflection.user_id == user_id,
            func.trim(WeeklyReflection.content) == content,
        ).exists()
    return select(User.id).where(User.id == user_id).exists()


def _source_owner_exists(
    *,
    user_id: int,
    source_type: str,
    source_id: int,
):
    """Build an ownership predicate without requiring content equality."""

    if source_type == "notes":
        return select(Day.id).where(
            Day.id == source_id,
            Day.user_id == user_id,
        ).exists()
    if source_type == "conversation":
        return select(ConversationEntry.id).join(
            Day, Day.id == ConversationEntry.day_id
        ).where(
            ConversationEntry.id == source_id,
            Day.user_id == user_id,
        ).exists()
    if source_type == "summaries":
        return select(SummaryArtifact.id).join(
            Day, Day.id == SummaryArtifact.day_id
        ).where(
            SummaryArtifact.id == source_id,
            Day.user_id == user_id,
        ).exists()
    if source_type == "threads":
        return select(CarryForwardItem.id).join(
            Day, Day.id == CarryForwardItem.origin_day_id
        ).where(
            CarryForwardItem.id == source_id,
            Day.user_id == user_id,
        ).exists()
    if source_type == "weekly_reflections":
        return select(WeeklyReflection.id).where(
            WeeklyReflection.id == source_id,
            WeeklyReflection.user_id == user_id,
        ).exists()
    return select(User.id).where(User.id == user_id).exists()


async def _source_is_current(
    db: AsyncSession,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
) -> bool:
    predicate = _source_current_exists(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    )
    return bool(await db.scalar(select(predicate)))


async def _safe_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        logger.warning("continuity embedding database rollback failed")


async def _clear_source_embedding(
    db: AsyncSession,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
) -> bool:
    """Remove a source row only while that source is still the requested one."""

    source_exists = _source_current_exists(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    )
    owner_exists = _source_owner_exists(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
    )
    statement = delete(ContinuityEmbedding).where(
        ContinuityEmbedding.user_id == user_id,
        ContinuityEmbedding.source_type == source_type,
        ContinuityEmbedding.source_id == source_id,
        or_(source_exists, ~owner_exists),
    )
    result = await db.execute(statement)
    await db.commit()
    return (getattr(result, "rowcount", 0) or 0) > 0


async def _prepare_placeholder(
    db: AsyncSession,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
    content_hash: str,
    day_id: int | None,
    source_date,
    retry_non_current: bool = False,
    return_id: bool = False,
) -> tuple[bool, bool] | tuple[bool, bool, int | None]:
    """Atomically claim a non-current row for one provider refresh."""

    if not await _source_is_current(
        db,
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    ):
        if not await db.scalar(
            select(_source_owner_exists(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
            ))
        ):
            await db.execute(
                delete(ContinuityEmbedding).where(
                    ContinuityEmbedding.user_id == user_id,
                    ContinuityEmbedding.source_type == source_type,
                    ContinuityEmbedding.source_id == source_id,
                )
            )
            await db.commit()
        else:
            await _safe_rollback(db)
        result = (False, False, None)
        return result if return_id else result[:2]

    if not await db.scalar(
        select(User.id).where(
            User.id == user_id,
            User.ai_processing_consent.is_(True),
        )
    ):
        await _clear_source_embedding(
            db,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            content=content,
        )
        result = (False, False, None)
        return result if return_id else result[:2]

    consent_exists = select(User.id).where(
        User.id == user_id,
        User.ai_processing_consent.is_(True),
    ).exists()
    source_exists = _source_current_exists(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    )
    placeholder_vector = [0.0] * CONTINUITY_EMBEDDING_DIMENSION
    placeholder_vector[0] = 1.0
    statement = pg_insert(ContinuityEmbedding).from_select(
        [
            "user_id",
            "source_type",
            "source_id",
            "day_id",
            "source_date",
            "content",
            "content_hash",
            "embedding_model",
            "embedding",
            "is_current",
        ],
        select(
            User.id,
            literal(source_type, type_=ContinuityEmbedding.source_type.type),
            literal(source_id, type_=ContinuityEmbedding.source_id.type),
            literal(day_id, type_=ContinuityEmbedding.day_id.type),
            literal(source_date, type_=ContinuityEmbedding.source_date.type),
            literal(content, type_=ContinuityEmbedding.content.type),
            literal(content_hash, type_=ContinuityEmbedding.content_hash.type),
            literal(
                settings.embedding_model,
                type_=ContinuityEmbedding.embedding_model.type,
            ),
            literal(
                placeholder_vector,
                type_=ContinuityEmbedding.embedding.type,
            ),
            literal(False, type_=ContinuityEmbedding.is_current.type),
        ).where(
            User.id == user_id,
            consent_exists,
            source_exists,
        ),
    )
    excluded = statement.excluded
    changed_content_or_model = (
        ContinuityEmbedding.content_hash.is_distinct_from(
            excluded.content_hash
        )
        | ContinuityEmbedding.embedding_model.is_distinct_from(
            excluded.embedding_model
        )
    )
    conflict_condition = changed_content_or_model
    if retry_non_current:
        retry_condition = and_(
            ContinuityEmbedding.is_current.is_(False),
            ContinuityEmbedding.updated_at
            < func.now()
            - text(f"INTERVAL '{EMBEDDING_RETRY_LEASE_SECONDS} seconds'"),
        )
        conflict_condition = or_(changed_content_or_model, retry_condition)
    statement = statement.on_conflict_do_update(
        index_elements=[
            ContinuityEmbedding.user_id,
            ContinuityEmbedding.source_type,
            ContinuityEmbedding.source_id,
        ],
        set_={
            "day_id": excluded.day_id,
            "source_date": excluded.source_date,
            "content": excluded.content,
            "content_hash": excluded.content_hash,
            "embedding_model": excluded.embedding_model,
            "embedding": excluded.embedding,
            "is_current": excluded.is_current,
            "updated_at": func.now(),
        },
        where=and_(consent_exists, source_exists, conflict_condition),
    ).returning(
        ContinuityEmbedding.id,
        ContinuityEmbedding.content_hash,
        ContinuityEmbedding.embedding_model,
        ContinuityEmbedding.is_current,
    )
    result = await db.execute(statement)
    claimed = result.first()
    await db.commit()
    if claimed is not None:
        result = (True, True, int(claimed[0]))
        return result if return_id else result[:2]

    existing = await db.scalar(
        select(ContinuityEmbedding).where(
            ContinuityEmbedding.user_id == user_id,
            ContinuityEmbedding.source_type == source_type,
            ContinuityEmbedding.source_id == source_id,
        )
    )
    existing_state = (
        (
            existing.is_current,
            existing.content_hash,
            existing.embedding_model,
            existing.id,
        )
        if existing is not None
        else None
    )
    await _safe_rollback(db)
    if (
        existing_state is not None
        and existing_state[0]
        and existing_state[1] == content_hash
        and existing_state[2] == settings.embedding_model
    ):
        result = (True, False, int(existing_state[3]))
        return result if return_id else result[:2]
    result = (False, False, None)
    return result if return_id else result[:2]


async def _consent_still_allows_embedding(
    db: AsyncSession,
    user_id: int,
) -> tuple[bool, bool]:
    result = await db.execute(
        select(
            User.ai_processing_consent,
            User.ai_redaction_enabled,
        ).where(User.id == user_id)
    )
    row = result.one_or_none()
    await db.rollback()
    if row is None:
        return False, True
    return bool(row[0]), bool(row[1])


async def _activate_embedding(
    db: AsyncSession,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
    content_hash: str,
    placeholder_id: int,
    day_id: int | None,
    source_date,
    vector: list[float],
) -> bool:
    consent_exists = select(User.id).where(
        User.id == user_id,
        User.ai_processing_consent.is_(True),
    ).exists()
    source_exists = _source_current_exists(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    )
    statement = (
        update(ContinuityEmbedding)
        .where(
            ContinuityEmbedding.id == placeholder_id,
            ContinuityEmbedding.user_id == user_id,
            ContinuityEmbedding.source_type == source_type,
            ContinuityEmbedding.source_id == source_id,
            ContinuityEmbedding.content_hash == content_hash,
            ContinuityEmbedding.embedding_model == settings.embedding_model,
            ContinuityEmbedding.is_current.is_(False),
            consent_exists,
            source_exists,
        )
        .values(
            day_id=day_id,
            source_date=source_date,
            content=content,
            content_hash=content_hash,
            embedding_model=settings.embedding_model,
            embedding=vector,
            is_current=True,
            updated_at=ai_service.utcnow(),
        )
    )
    result = await db.execute(statement)
    await db.commit()
    return result.rowcount == 1


def _caller_async_engine(
    caller: AsyncSession | AsyncConnection,
) -> tuple[AsyncEngine, bool]:
    """Resolve the caller's database without borrowing its transaction."""

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
        raise RuntimeError("embedding session has no usable database bind")
    derived_engine = create_async_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    from ..extensions import configure_pgvector_async_engine

    configure_pgvector_async_engine(derived_engine)
    return derived_engine, True


async def sync_source_embedding(
    db: AsyncSession | AsyncConnection,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
    day_id: int | None = None,
    source_date=None,
    client: httpx.AsyncClient | None = None,
    retry_non_current: bool = False,
) -> bool:
    """Refresh a source embedding without borrowing the caller's session.

    Source services intentionally call this after their own commit.  A
    separate session keeps optional placeholder/provider failures from
    rolling back that session and expiring ORM instances the caller still
    needs to serialize.  Lightweight fakes can still exercise the lifecycle
    directly in unit tests.
    """

    if isinstance(db, (AsyncSession, AsyncConnection)):
        try:
            if not await ai_service.release_read_transaction(db):
                logger.warning(
                    "continuity embedding skipped for caller with pending work"
                )
                return False
        except Exception:
            logger.warning("continuity embedding caller transaction release failed")
            return False
        try:
            embedding_engine, owns_engine = _caller_async_engine(db)
            try:
                embedding_session = async_sessionmaker(
                    embedding_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                async with embedding_session() as embedding_db:
                    return await _sync_source_embedding(
                        embedding_db,
                        user_id=user_id,
                        source_type=source_type,
                        source_id=source_id,
                        content=content,
                        day_id=day_id,
                        source_date=source_date,
                        client=client,
                        retry_non_current=retry_non_current,
                    )
            finally:
                if owns_engine:
                    await embedding_engine.dispose()
        except Exception:
            logger.warning("continuity embedding session setup failed")
            return False
    return await _sync_source_embedding(
        db,
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        content=content,
        day_id=day_id,
        source_date=source_date,
        client=client,
        retry_non_current=retry_non_current,
    )


async def _sync_source_embedding(
    db: AsyncSession,
    *,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str,
    day_id: int | None = None,
    source_date=None,
    client: httpx.AsyncClient | None = None,
    retry_non_current: bool = False,
) -> bool:
    """Best-effort two-phase refresh with a committed placeholder and CAS.

    The source service commits before calling this function.  The placeholder
    transaction is committed before provider HTTP, and activation only updates
    the exact hash/source that produced the vector.  A purge or newer write can
    therefore make an in-flight provider response a harmless no-op.
    """

    stored_content = _normalized_content(content)
    digest = _content_hash(stored_content)
    if (
        not stored_content
        or not settings.ai_enabled
        or not settings.embedding_enabled
    ):
        try:
            await _clear_source_embedding(
                db,
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                content=stored_content,
            )
        except Exception:
            await _safe_rollback(db)
            logger.warning("continuity embedding cleanup transaction failed")
        return False

    try:
        claim = await _prepare_placeholder(
            db,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            content=stored_content,
            content_hash=digest,
            day_id=day_id,
            source_date=source_date,
            return_id=True,
            retry_non_current=retry_non_current,
        )
        prepared, needs_provider, placeholder_id = claim
    except Exception:
        await _safe_rollback(db)
        logger.warning("continuity embedding placeholder transaction failed")
        return False
    if not prepared:
        return False
    if not needs_provider:
        return True
    if placeholder_id is None:
        logger.warning("continuity embedding claim did not return a row id")
        return False

    try:
        consent, redaction_enabled = await _consent_still_allows_embedding(
            db, user_id
        )
    except Exception:
        await _safe_rollback(db)
        logger.warning("continuity embedding consent check failed")
        return False
    if not consent or not settings.ai_enabled or not settings.embedding_enabled:
        return False

    try:
        vector = await embed_text(
            stored_content,
            input_type="passage",
            redaction_enabled=redaction_enabled,
            client=client,
        )
    except Exception as error:
        logger.warning(
            "continuity embedding refresh failed source_type=%s source_id=%s reason=%s",
            source_type,
            source_id,
            ai_service._safe_provider_error(error),
        )
        return False

    try:
        return await _activate_embedding(
            db,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            content=stored_content,
            content_hash=digest,
            placeholder_id=placeholder_id,
            day_id=day_id,
            source_date=source_date,
            vector=vector,
        )
    except Exception:
        await _safe_rollback(db)
        logger.warning("continuity embedding activation transaction failed")
        return False


async def backfill_embeddings(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    batch_size: int = 50,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Retry a bounded batch of missing or non-current source embeddings.

    Candidates are materialized before the session is rolled back, then each
    refresh uses the same placeholder/CAS lifecycle as normal writes. A later
    invocation retries provider failures because non-current rows remain
    non-current; no worker or durable queue is required.
    """

    if not 1 <= batch_size <= MAX_BACKFILL_BATCH:
        raise ValueError(
            f"batch_size must be between 1 and {MAX_BACKFILL_BATCH}"
        )
    candidates: list[dict] = []
    seen_candidates: set[tuple[str, int]] = set()

    def remaining() -> int:
        return batch_size - len(candidates)

    def add_candidate(
        *,
        existing,
        source_type: str,
        content: str | None,
        source_user_id: int,
        source_id: int,
        day_id: int | None,
        source_date,
    ) -> None:
        key = (source_type, source_id)
        if (
            remaining() <= 0
            or key in seen_candidates
            or not _needs_backfill(content, existing)
        ):
            return
        seen_candidates.add(key)
        candidates.append(
            {
                "user_id": source_user_id,
                "source_type": source_type,
                "source_id": source_id,
                "content": content or "",
                "day_id": day_id,
                "source_date": source_date,
                "retry_non_current": existing is not None
                and not existing.is_current,
            }
        )

    try:
        async def scan_rows(statement, id_column, row_id, add_row) -> None:
            cursor = 0
            while remaining() > 0:
                page = await db.execute(
                    statement.where(id_column > cursor)
                    .order_by(id_column)
                    .limit(BACKFILL_SOURCE_SCAN_LIMIT)
                )
                rows = page.all()
                if not rows:
                    return
                for row in rows:
                    add_row(row)
                    if remaining() <= 0:
                        return
                next_cursor = max(row_id(row) for row in rows)
                if next_cursor <= cursor:
                    return
                cursor = next_cursor
                if len(rows) < BACKFILL_SOURCE_SCAN_LIMIT:
                    return

        day_filters = []
        if user_id is not None:
            day_filters.append(Day.user_id == user_id)
        day_statement = (
            select(Day, ContinuityEmbedding)
            .outerjoin(
                ContinuityEmbedding,
                and_(
                    ContinuityEmbedding.user_id == Day.user_id,
                    ContinuityEmbedding.source_type == "notes",
                    ContinuityEmbedding.source_id == Day.id,
                ),
            )
            .where(*day_filters)
        )

        def add_day(row) -> None:
            day, existing = row
            add_candidate(
                existing=existing,
                source_type="notes",
                content=day.daily_note,
                source_user_id=day.user_id,
                source_id=day.id,
                day_id=day.id,
                source_date=day.date,
            )

        await scan_rows(
            day_statement.where(_sql_needs_backfill(Day.daily_note)),
            Day.id,
            lambda row: row[0].id,
            add_day,
        )

        conversation_filters = []
        if user_id is not None:
            conversation_filters.append(Day.user_id == user_id)
        conversation_statement = (
            select(ConversationEntry, Day, ContinuityEmbedding)
            .join(Day, Day.id == ConversationEntry.day_id)
            .outerjoin(
                ContinuityEmbedding,
                and_(
                    ContinuityEmbedding.user_id == Day.user_id,
                    ContinuityEmbedding.source_type == "conversation",
                    ContinuityEmbedding.source_id == ConversationEntry.id,
                ),
            )
            .where(*conversation_filters)
        )

        def add_conversation(row) -> None:
            entry, day, existing = row
            add_candidate(
                existing=existing,
                source_type="conversation",
                content=entry.content,
                source_user_id=day.user_id,
                source_id=entry.id,
                day_id=day.id,
                source_date=day.date,
            )

        await scan_rows(
            conversation_statement.where(
                _sql_needs_backfill(ConversationEntry.content)
            ),
            ConversationEntry.id,
            lambda row: row[0].id,
            add_conversation,
        )

        summary_filters = [SummaryArtifact.kind == "daily"]
        if user_id is not None:
            summary_filters.append(Day.user_id == user_id)
        summary_statement = (
            select(SummaryArtifact, Day, ContinuityEmbedding)
            .join(Day, Day.id == SummaryArtifact.day_id)
            .outerjoin(
                ContinuityEmbedding,
                and_(
                    ContinuityEmbedding.user_id == Day.user_id,
                    ContinuityEmbedding.source_type == "summaries",
                    ContinuityEmbedding.source_id == SummaryArtifact.id,
                ),
            )
            .where(*summary_filters)
        )

        def add_summary(row) -> None:
            artifact, day, existing = row
            add_candidate(
                existing=existing,
                source_type="summaries",
                content=artifact.content,
                source_user_id=day.user_id,
                source_id=artifact.id,
                day_id=day.id,
                source_date=day.date,
            )

        await scan_rows(
            summary_statement.where(
                _sql_needs_backfill(SummaryArtifact.content)
            ),
            SummaryArtifact.id,
            lambda row: row[0].id,
            add_summary,
        )

        thread_filters = []
        if user_id is not None:
            thread_filters.append(Day.user_id == user_id)
        thread_statement = (
            select(CarryForwardItem, Day, ContinuityEmbedding)
            .join(Day, Day.id == CarryForwardItem.origin_day_id)
            .outerjoin(
                ContinuityEmbedding,
                and_(
                    ContinuityEmbedding.user_id == Day.user_id,
                    ContinuityEmbedding.source_type == "threads",
                    ContinuityEmbedding.source_id == CarryForwardItem.id,
                ),
            )
            .where(*thread_filters)
        )

        def add_thread(row) -> None:
            item, day, existing = row
            add_candidate(
                existing=existing,
                source_type="threads",
                content=item.content,
                source_user_id=day.user_id,
                source_id=item.id,
                day_id=day.id,
                source_date=day.date,
            )

        await scan_rows(
            thread_statement.where(
                _sql_needs_backfill(CarryForwardItem.content)
            ),
            CarryForwardItem.id,
            lambda row: row[0].id,
            add_thread,
        )

        reflection_filters = []
        if user_id is not None:
            reflection_filters.append(
                WeeklyReflection.user_id == user_id
            )
        reflection_statement = (
            select(WeeklyReflection, ContinuityEmbedding)
            .outerjoin(
                ContinuityEmbedding,
                and_(
                    ContinuityEmbedding.user_id
                    == WeeklyReflection.user_id,
                    ContinuityEmbedding.source_type
                    == "weekly_reflections",
                    ContinuityEmbedding.source_id == WeeklyReflection.id,
                ),
            )
            .where(*reflection_filters)
        )

        def add_reflection(row) -> None:
            reflection, existing = row
            add_candidate(
                existing=existing,
                source_type="weekly_reflections",
                content=reflection.content,
                source_user_id=reflection.user_id,
                source_id=reflection.id,
                day_id=None,
                source_date=reflection.week_start,
            )

        await scan_rows(
            reflection_statement.where(
                _sql_needs_backfill(WeeklyReflection.content)
            ),
            WeeklyReflection.id,
            lambda row: row[0].id,
            add_reflection,
        )

        if remaining() > 0:
            await scan_rows(
                day_statement.where(_sql_hash_check(Day.daily_note)),
                Day.id,
                lambda row: row[0].id,
                add_day,
            )
        if remaining() > 0:
            await scan_rows(
                conversation_statement.where(
                    _sql_hash_check(ConversationEntry.content)
                ),
                ConversationEntry.id,
                lambda row: row[0].id,
                add_conversation,
            )
        if remaining() > 0:
            await scan_rows(
                summary_statement.where(
                    _sql_hash_check(SummaryArtifact.content)
                ),
                SummaryArtifact.id,
                lambda row: row[0].id,
                add_summary,
            )
        if remaining() > 0:
            await scan_rows(
                thread_statement.where(
                    _sql_hash_check(CarryForwardItem.content)
                ),
                CarryForwardItem.id,
                lambda row: row[0].id,
                add_thread,
            )
        if remaining() > 0:
            await scan_rows(
                reflection_statement.where(
                    _sql_hash_check(WeeklyReflection.content)
                ),
                WeeklyReflection.id,
                lambda row: row[0].id,
                add_reflection,
            )
        await db.rollback()
    except SQLAlchemyError:
        await _safe_rollback(db)
        logger.warning("continuity embedding backfill query failed")
        return {"attempted": 0, "refreshed": 0, "failed": 1}

    refreshed = 0
    failed = 0
    owns_client = client is None
    try:
        if candidates and client is None:
            client = httpx.AsyncClient(
                timeout=settings.embedding_request_timeout_seconds
            )
        for candidate in candidates:
            try:
                if await _sync_source_embedding(db, client=client, **candidate):
                    refreshed += 1
                else:
                    failed += 1
            except Exception:
                await _safe_rollback(db)
                failed += 1
    finally:
        if owns_client and client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.warning("continuity embedding client cleanup failed")
    return {
        "attempted": len(candidates),
        "refreshed": refreshed,
        "failed": failed,
    }

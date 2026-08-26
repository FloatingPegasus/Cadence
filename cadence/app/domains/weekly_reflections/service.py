import hashlib
import json
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..continuity import service as continuity_service
from ...persistence.models.weekly_reflection import WeeklyReflection
from ...services import ai as ai_service
from ...services import embeddings as embedding_service
from ...services.continuity_lock import acquire_continuity_lock


PROMPT_VERSION = "weekly-reflection-v1"
SOURCE_CHANGED_MESSAGE = "Source changed while generating; please retry."


def _session_factory(db: AsyncSession):
    bind = getattr(db, "bind", None)
    if bind is None:
        raise RuntimeError("reflection generation session has no database bind")
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _reflection_state(reflection: WeeklyReflection | None) -> dict | None:
    if reflection is None:
        return None
    return {
        "id": reflection.id,
        "updated_at": reflection.updated_at,
        "content": reflection.content,
        "source_fingerprint": reflection.source_fingerprint,
        "is_user_edited": reflection.is_user_edited,
    }


async def _initial_generation_state(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
) -> tuple[date, dict, str, dict | None]:
    factory = _session_factory(db)
    async with factory() as snapshot_db:
        await acquire_continuity_lock(snapshot_db, user_id)
        week_start, snapshot = await build_source_snapshot(
            snapshot_db,
            user_id,
            anchor_date,
        )
        source_fingerprint, _ = fingerprint(snapshot)
        reflection = await snapshot_db.scalar(
            select(WeeklyReflection).where(
                WeeklyReflection.user_id == user_id,
                WeeklyReflection.week_start == week_start,
            )
        )
        reflection_state = _reflection_state(reflection)
        await snapshot_db.rollback()
        return week_start, snapshot, source_fingerprint, reflection_state


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


async def build_source_snapshot(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
) -> tuple[date, dict]:
    week = await continuity_service.get_week(
        db,
        user_id,
        _coerce_date(anchor_date),
    )
    return date.fromisoformat(week["week_start"]), week


def fingerprint(snapshot: dict) -> tuple[str, str]:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest(), encoded


def serialize(
    reflection: WeeklyReflection | None,
    current_source_fingerprint: str | None = None,
) -> dict | None:
    if reflection is None:
        return None
    return {
        "id": reflection.id,
        "week_start": reflection.week_start.isoformat(),
        "week_end": (reflection.week_start + timedelta(days=6)).isoformat(),
        "content": reflection.content,
        "provider": reflection.provider,
        "model": reflection.model,
        "prompt_version": reflection.prompt_version,
        "source_fingerprint": reflection.source_fingerprint,
        "is_stale": (
            current_source_fingerprint is not None
            and reflection.source_fingerprint
            != current_source_fingerprint
        ),
        "is_user_edited": reflection.is_user_edited,
        "generated_at": (
            reflection.generated_at.isoformat()
            if reflection.generated_at
            else None
        ),
        "updated_at": reflection.updated_at.isoformat(),
    }


async def get_weekly_reflection(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
) -> dict | None:
    await acquire_continuity_lock(db, user_id)
    week_start, snapshot = await build_source_snapshot(
        db,
        user_id,
        anchor_date,
    )
    current_fingerprint, _ = fingerprint(snapshot)
    reflection = await db.scalar(
        select(WeeklyReflection).where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start == week_start,
        )
    )
    return serialize(reflection, current_fingerprint)


async def list_weekly_reflections(
    db: AsyncSession,
    user_id: int,
    limit: int = 12,
) -> list[dict]:
    result = await db.execute(
        select(WeeklyReflection)
        .where(WeeklyReflection.user_id == user_id)
        .order_by(WeeklyReflection.week_start.desc())
        .limit(limit)
    )
    return [
        {
            "id": reflection.id,
            "week_start": reflection.week_start.isoformat(),
            "week_end": (
                reflection.week_start + timedelta(days=6)
            ).isoformat(),
            "excerpt": " ".join(reflection.content.split())[:240],
            "is_user_edited": reflection.is_user_edited,
            "model": reflection.model,
            "updated_at": reflection.updated_at.isoformat(),
        }
        for reflection in result.scalars()
    ]


async def save_manual_reflection(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
    content: str,
) -> dict:
    await acquire_continuity_lock(db, user_id)
    week_start, snapshot = await build_source_snapshot(
        db,
        user_id,
        anchor_date,
    )
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    now = ai_service.utcnow()
    statement = pg_insert(WeeklyReflection).values(
        user_id=user_id,
        week_start=week_start,
        content=content,
        provider=None,
        model=None,
        prompt_version=PROMPT_VERSION,
        source_fingerprint=source_fingerprint,
        source_snapshot=source_snapshot,
        is_user_edited=True,
        generated_at=None,
        updated_at=now,
    )
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[WeeklyReflection.user_id, WeeklyReflection.week_start],
        set_={
            "content": excluded.content,
            "provider": excluded.provider,
            "model": excluded.model,
            "prompt_version": excluded.prompt_version,
            "source_fingerprint": excluded.source_fingerprint,
            "source_snapshot": excluded.source_snapshot,
            "is_user_edited": excluded.is_user_edited,
            "generated_at": excluded.generated_at,
            "updated_at": excluded.updated_at,
        },
    )
    await db.execute(statement)
    await db.commit()
    reflection = await db.scalar(
        select(WeeklyReflection).where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start == week_start,
        )
    )
    if reflection is None:
        raise RuntimeError("reflection disappeared after manual save")
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="weekly_reflections",
        source_id=reflection.id,
        source_date=reflection.week_start,
        content=reflection.content,
    )
    return serialize(reflection, source_fingerprint)


async def generate_weekly_reflection(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
    *,
    replace_edited: bool = False,
) -> dict:
    (
        week_start,
        snapshot,
        initial_source_fingerprint,
        initial_state,
    ) = await _initial_generation_state(db, user_id, anchor_date)
    if initial_state and initial_state["is_user_edited"] and not replace_edited:
        raise ValueError("Edited reflection requires explicit replacement")
    if not await ai_service.release_read_transaction(db):
        raise ai_service.AIConfigurationError(
            "AI provider calls require a caller session without pending work"
        )

    result = await ai_service.chat_with_fallback(
        db,
        task="summary",
        messages=[
            {
                "role": "system",
                "content": (
                    "Create a concise, non-judgmental weekly continuity "
                    "reflection. Identify meaningful movement, friction, "
                    "context worth resuming, and unresolved threads. "
                    "Preserve uncertainty. Do not invent facts, score the "
                    "user, diagnose them, or prescribe optimization."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False),
            },
        ],
        max_tokens=700,
        temperature=0.2,
        user_id=user_id,
    )
    factory = _session_factory(db)
    async with factory() as write_db:
        await acquire_continuity_lock(write_db, user_id)
        current_week_start, current_snapshot = await build_source_snapshot(
            write_db,
            user_id,
            anchor_date,
        )
        source_fingerprint, source_snapshot = fingerprint(current_snapshot)
        if source_fingerprint != initial_source_fingerprint:
            await write_db.rollback()
            raise ValueError(SOURCE_CHANGED_MESSAGE)

        now = ai_service.utcnow()
        generated_values = {
            "content": result["content"],
            "provider": result["provider"],
            "model": result["model"],
            "prompt_version": PROMPT_VERSION,
            "source_fingerprint": source_fingerprint,
            "source_snapshot": source_snapshot,
            "is_user_edited": False,
            "generated_at": now,
            "updated_at": now,
        }
        if initial_state is None:
            statement = pg_insert(WeeklyReflection).values(
                user_id=user_id,
                week_start=current_week_start,
                **generated_values,
            )
            result_row = await write_db.execute(
                statement.on_conflict_do_nothing(
                    index_elements=[
                        WeeklyReflection.user_id,
                        WeeklyReflection.week_start,
                    ]
                ).returning(WeeklyReflection.id)
            )
            wrote_generated = result_row.scalar_one_or_none() is not None
        else:
            result_row = await write_db.execute(
                update(WeeklyReflection)
                .where(
                    WeeklyReflection.id == initial_state["id"],
                    WeeklyReflection.updated_at.is_not_distinct_from(
                        initial_state["updated_at"]
                    ),
                    WeeklyReflection.content == initial_state["content"],
                    WeeklyReflection.source_fingerprint
                    == initial_state["source_fingerprint"],
                    WeeklyReflection.is_user_edited
                    == initial_state["is_user_edited"],
                )
                .values(**generated_values)
            )
            wrote_generated = result_row.rowcount == 1
        await write_db.commit()
        reflection = await write_db.scalar(
            select(WeeklyReflection).where(
                WeeklyReflection.user_id == user_id,
                WeeklyReflection.week_start == current_week_start,
            )
        )
        if reflection is None:
            raise RuntimeError("reflection disappeared after generation")
        if wrote_generated:
            await embedding_service.sync_source_embedding(
                write_db,
                user_id=user_id,
                source_type="weekly_reflections",
                source_id=reflection.id,
                source_date=reflection.week_start,
                content=reflection.content,
            )
        return serialize(reflection, source_fingerprint)

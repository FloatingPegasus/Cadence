import hashlib
import json
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..days.service import get_or_create_day
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.hour_log import HourLog
from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.day import Day
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.user_goal import UserGoal
from ...services import ai as ai_service
from ...services import embeddings as embedding_service
from ...services.continuity_lock import acquire_continuity_lock


PROMPT_VERSION = "daily-summary-v2"
SOURCE_CHANGED_MESSAGE = "Source changed while generating; please retry."


def _session_factory(db: AsyncSession):
    bind = getattr(db, "bind", None)
    if bind is None:
        raise RuntimeError("summary generation session has no database bind")
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _artifact_state(artifact: SummaryArtifact | None) -> dict | None:
    if artifact is None:
        return None
    return {
        "id": artifact.id,
        "updated_at": artifact.updated_at,
        "content": artifact.content,
        "source_fingerprint": artifact.source_fingerprint,
        "is_user_edited": artifact.is_user_edited,
    }


async def _initial_generation_state(
    db: AsyncSession,
    user_id: int,
    target_date: date,
) -> tuple[int, dict, dict | None]:
    factory = _session_factory(db)
    async with factory() as snapshot_db:
        await acquire_continuity_lock(snapshot_db, user_id)
        day, snapshot = await build_source_snapshot(
            snapshot_db,
            user_id,
            target_date,
        )
        artifact = await snapshot_db.scalar(
            select(SummaryArtifact).where(
                SummaryArtifact.day_id == day.id,
                SummaryArtifact.kind == "daily",
            )
        )
        await snapshot_db.commit()
        return day.id, snapshot, _artifact_state(artifact)


async def build_source_snapshot(
    db: AsyncSession, user_id: int, target_date: date
) -> tuple[object, dict]:
    day = await get_or_create_day(db, user_id, target_date)
    checkin = await db.scalar(
        select(DailyCheckin).where(DailyCheckin.day_id == day.id)
    )
    conversation_result = await db.execute(
        select(ConversationEntry)
        .where(ConversationEntry.day_id == day.id)
        .order_by(ConversationEntry.created_at.desc())
        .limit(30)
    )
    entries = list(reversed(conversation_result.scalars().all()))
    habit_result = await db.execute(
        select(Habit.name)
        .join(HabitLog, HabitLog.habit_id == Habit.id)
        .where(HabitLog.day_id == day.id)
        .order_by(Habit.name)
    )
    hour_rows = await db.scalars(
        select(HourLog)
        .where(HourLog.day_id == day.id)
        .order_by(HourLog.hour)
    )
    goal_rows = await db.scalars(
        select(UserGoal)
        .where(UserGoal.user_id == user_id)
        .order_by(UserGoal.sort_order, UserGoal.id)
    )
    snapshot = {
        "date": day.date.isoformat(),
        "daily_note": (day.daily_note or "")[:20_000],
        "checkin": {
            field: getattr(checkin, field) if checkin else None
            for field in (
                "sleep_hours",
                "sleep_quality",
                "energy_level",
                "focus_quality",
                "emotional_state",
                "recovery_quality",
                "reentry_success",
                "drift_minutes",
                "notes",
            )
        },
        "completed_habits": list(habit_result.scalars().all()),
        "hours": [
            {"hour": row.hour, "content": row.content[:1_000]}
            for row in hour_rows
            if row.content.strip()
        ],
        "goals": [
            {"kind": goal.kind, "title": goal.title}
            for goal in goal_rows
        ],
        "conversation": [
            {"role": entry.role, "content": entry.content[:4_000]}
            for entry in entries
        ],
    }
    return day, snapshot


def fingerprint(snapshot: dict) -> tuple[str, str]:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest(), encoded


def serialize(
    artifact: SummaryArtifact | None,
    current_source_fingerprint: str | None = None,
) -> dict | None:
    if artifact is None:
        return None
    return {
        "id": artifact.id,
        "kind": artifact.kind,
        "content": artifact.content,
        "provider": artifact.provider,
        "model": artifact.model,
        "prompt_version": artifact.prompt_version,
        "source_fingerprint": artifact.source_fingerprint,
        "is_stale": (
            current_source_fingerprint is not None
            and artifact.source_fingerprint != current_source_fingerprint
        ),
        "is_user_edited": artifact.is_user_edited,
        "generated_at": (
            artifact.generated_at.isoformat()
            if artifact.generated_at
            else None
        ),
        "updated_at": artifact.updated_at.isoformat(),
    }


async def get_daily_summary(
    db: AsyncSession, user_id: int, target_date: date
) -> dict | None:
    day_exists = await db.scalar(
        select(Day.id).where(Day.user_id == user_id, Day.date == target_date)
    )
    if day_exists is None:
        return None
    day, snapshot = await build_source_snapshot(db, user_id, target_date)
    current_source_fingerprint, _ = fingerprint(snapshot)
    artifact = await db.scalar(
        select(SummaryArtifact).where(
            SummaryArtifact.day_id == day.id,
            SummaryArtifact.kind == "daily",
        )
    )
    return serialize(artifact, current_source_fingerprint)


async def save_manual_summary(
    db: AsyncSession, user_id: int, target_date: date, content: str
) -> dict:
    await acquire_continuity_lock(db, user_id)
    day, snapshot = await build_source_snapshot(db, user_id, target_date)
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    now = ai_service.utcnow()
    statement = pg_insert(SummaryArtifact).values(
        day_id=day.id,
        kind="daily",
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
        index_elements=[SummaryArtifact.day_id, SummaryArtifact.kind],
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
    artifact = await db.scalar(
        select(SummaryArtifact).where(
            SummaryArtifact.day_id == day.id,
            SummaryArtifact.kind == "daily",
        )
    )
    if artifact is None:
        raise RuntimeError("summary disappeared after manual save")
    await embedding_service.sync_source_embedding(
        db,
        user_id=user_id,
        source_type="summaries",
        source_id=artifact.id,
        day_id=day.id,
        source_date=day.date,
        content=artifact.content,
    )
    return serialize(artifact, source_fingerprint)


async def generate_daily_summary(
    db: AsyncSession,
    user_id: int,
    target_date: date,
    *,
    replace_edited: bool = False,
) -> dict:
    initial_day_id, snapshot, initial_state = await _initial_generation_state(
        db,
        user_id,
        target_date,
    )
    if initial_state and initial_state["is_user_edited"] and not replace_edited:
        raise ValueError("Edited summary requires explicit replacement")
    initial_source_fingerprint, _ = fingerprint(snapshot)

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
                    "Write a concise daily review from the supplied record. "
                    "Use hours, completed habits, and goals when present. "
                    "Do not invent hours, progress, or a diagnosis. "
                    "End with two to four suggestions for tomorrow. "
                    "Do not add a title."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False),
            },
        ],
        max_tokens=500,
        temperature=0.2,
        user_id=user_id,
    )
    factory = _session_factory(db)
    async with factory() as write_db:
        await acquire_continuity_lock(write_db, user_id)
        current_day, current_snapshot = await build_source_snapshot(
            write_db,
            user_id,
            target_date,
        )
        source_fingerprint, source_snapshot = fingerprint(current_snapshot)
        if (
            current_day.id != initial_day_id
            or source_fingerprint != initial_source_fingerprint
        ):
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
            statement = pg_insert(SummaryArtifact).values(
                day_id=current_day.id,
                kind="daily",
                **generated_values,
            )
            result_row = await write_db.execute(
                statement.on_conflict_do_nothing(
                    index_elements=[
                        SummaryArtifact.day_id,
                        SummaryArtifact.kind,
                    ]
                ).returning(SummaryArtifact.id)
            )
            wrote_generated = result_row.scalar_one_or_none() is not None
        else:
            result_row = await write_db.execute(
                update(SummaryArtifact)
                .where(
                    SummaryArtifact.id == initial_state["id"],
                    SummaryArtifact.updated_at.is_not_distinct_from(
                        initial_state["updated_at"]
                    ),
                    SummaryArtifact.content == initial_state["content"],
                    SummaryArtifact.source_fingerprint
                    == initial_state["source_fingerprint"],
                    SummaryArtifact.is_user_edited
                    == initial_state["is_user_edited"],
                )
                .values(**generated_values)
            )
            wrote_generated = result_row.rowcount == 1
        await write_db.commit()
        artifact = await write_db.scalar(
            select(SummaryArtifact).where(
                SummaryArtifact.day_id == current_day.id,
                SummaryArtifact.kind == "daily",
            )
        )
        if artifact is None:
            raise RuntimeError("summary disappeared after generation")
        if wrote_generated:
            await embedding_service.sync_source_embedding(
                write_db,
                user_id=user_id,
                source_type="summaries",
                source_id=artifact.id,
                day_id=current_day.id,
                source_date=current_day.date,
                content=artifact.content,
            )
        return serialize(artifact, source_fingerprint)

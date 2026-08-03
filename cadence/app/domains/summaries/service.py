import hashlib
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..days.service import get_or_create_day
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.habit import Habit
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.day import Day
from ...persistence.models.summary_artifact import SummaryArtifact
from ...services import ai as ai_service


PROMPT_VERSION = "daily-summary-v1"


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
    day, snapshot = await build_source_snapshot(db, user_id, target_date)
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    artifact = await db.scalar(
        select(SummaryArtifact).where(
            SummaryArtifact.day_id == day.id,
            SummaryArtifact.kind == "daily",
        )
    )
    if artifact is None:
        artifact = SummaryArtifact(
            day_id=day.id, kind="daily", prompt_version=PROMPT_VERSION
        )
        db.add(artifact)
    artifact.content = content
    artifact.provider = None
    artifact.model = None
    artifact.source_fingerprint = source_fingerprint
    artifact.source_snapshot = source_snapshot
    artifact.is_user_edited = True
    artifact.generated_at = None
    await db.commit()
    await db.refresh(artifact)
    return serialize(artifact, source_fingerprint)


async def generate_daily_summary(
    db: AsyncSession,
    user_id: int,
    target_date: date,
    *,
    replace_edited: bool = False,
) -> dict:
    day, snapshot = await build_source_snapshot(db, user_id, target_date)
    artifact = await db.scalar(
        select(SummaryArtifact).where(
            SummaryArtifact.day_id == day.id,
            SummaryArtifact.kind == "daily",
        )
    )
    if artifact and artifact.is_user_edited and not replace_edited:
        raise ValueError("Edited summary requires explicit replacement")

    result = await ai_service.chat_with_fallback(
        db,
        task="summary",
        messages=[
            {
                "role": "system",
                "content": (
                    "Create a concise, non-judgmental continuity summary. "
                    "Preserve uncertainty. Cover what moved, what felt "
                    "difficult, and what may deserve carrying forward. "
                    "Do not invent facts or diagnose the user."
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
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    if artifact is None:
        artifact = SummaryArtifact(
            day_id=day.id, kind="daily", prompt_version=PROMPT_VERSION
        )
        db.add(artifact)
    artifact.content = result["content"]
    artifact.provider = result["provider"]
    artifact.model = result["model"]
    artifact.source_fingerprint = source_fingerprint
    artifact.source_snapshot = source_snapshot
    artifact.is_user_edited = False
    artifact.generated_at = ai_service.utcnow()
    await db.commit()
    await db.refresh(artifact)
    return serialize(artifact, source_fingerprint)

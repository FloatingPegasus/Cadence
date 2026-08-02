import hashlib
import json
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..continuity import service as continuity_service
from ...persistence.models.weekly_reflection import WeeklyReflection
from ...services import ai as ai_service


PROMPT_VERSION = "weekly-reflection-v1"


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
    week_start, snapshot = await build_source_snapshot(
        db,
        user_id,
        anchor_date,
    )
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    reflection = await db.scalar(
        select(WeeklyReflection).where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start == week_start,
        )
    )
    if reflection is None:
        reflection = WeeklyReflection(
            user_id=user_id,
            week_start=week_start,
            prompt_version=PROMPT_VERSION,
        )
        db.add(reflection)
    reflection.content = content
    reflection.provider = None
    reflection.model = None
    reflection.source_fingerprint = source_fingerprint
    reflection.source_snapshot = source_snapshot
    reflection.is_user_edited = True
    reflection.generated_at = None
    await db.commit()
    await db.refresh(reflection)
    return serialize(reflection, source_fingerprint)


async def generate_weekly_reflection(
    db: AsyncSession,
    user_id: int,
    anchor_date: date | str,
    *,
    replace_edited: bool = False,
) -> dict:
    week_start, snapshot = await build_source_snapshot(
        db,
        user_id,
        anchor_date,
    )
    reflection = await db.scalar(
        select(WeeklyReflection).where(
            WeeklyReflection.user_id == user_id,
            WeeklyReflection.week_start == week_start,
        )
    )
    if reflection and reflection.is_user_edited and not replace_edited:
        raise ValueError("Edited reflection requires explicit replacement")

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
    source_fingerprint, source_snapshot = fingerprint(snapshot)
    if reflection is None:
        reflection = WeeklyReflection(
            user_id=user_id,
            week_start=week_start,
            prompt_version=PROMPT_VERSION,
        )
        db.add(reflection)
    reflection.content = result["content"]
    reflection.provider = result["provider"]
    reflection.model = result["model"]
    reflection.source_fingerprint = source_fingerprint
    reflection.source_snapshot = source_snapshot
    reflection.is_user_edited = False
    reflection.generated_at = ai_service.utcnow()
    await db.commit()
    await db.refresh(reflection)
    return serialize(reflection, source_fingerprint)

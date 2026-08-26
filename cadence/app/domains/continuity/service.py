from datetime import date, timedelta
import logging

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...persistence.models.carry_forward_item import CarryForwardItem
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit_log import HabitLog
from ...persistence.models.summary_artifact import SummaryArtifact
from ...persistence.models.weekly_reflection import WeeklyReflection
from ...persistence.models.continuity_embedding import ContinuityEmbedding
from ...persistence.models.user import User
from ...services import embeddings as embedding_service


logger = logging.getLogger("cadence.continuity")


class ContextFilterNotFoundError(LookupError):
    pass


async def _safe_search_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        logger.warning("semantic continuity search rollback failed")


async def _enable_iterative_hnsw_scan(
    db: AsyncSession,
) -> bool | None:
    """Use iterative HNSW, or configure an exact sequential scan fallback."""

    try:
        await db.execute(
            text("SET LOCAL hnsw.iterative_scan = 'strict_order'")
        )
        return True
    except Exception:
        await _safe_search_rollback(db)
        try:
            await db.execute(text("SET LOCAL enable_indexscan = off"))
            await db.execute(text("SET LOCAL enable_bitmapscan = off"))
        except Exception:
            await _safe_search_rollback(db)
            return None
        return False


def _week_bounds(anchor_date: date) -> tuple[date, date]:
    week_start = anchor_date - timedelta(days=anchor_date.weekday())
    return week_start, week_start + timedelta(days=6)


def _like_pattern(term: str) -> str:
    escaped = (
        term.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _empty_search_payload(
    term: str,
    source: str,
    start_date: date,
    end_date: date,
    context_id: int | None,
) -> dict:
    return {
        "query": term,
        "source": source,
        "context_id": context_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "results": [],
    }


def _excerpt(content: str, term: str, length: int = 220) -> str:
    compact = " ".join(content.split())
    match_at = compact.casefold().find(term.casefold())
    if match_at < 0 or len(compact) <= length:
        return compact[:length]
    start = max(0, match_at - length // 3)
    end = min(len(compact), start + length)
    return (
        ("…" if start else "")
        + compact[start:end]
        + ("…" if end < len(compact) else "")
    )


def _preview(content: str | None, length: int) -> str:
    return " ".join((content or "").split())[:length]


async def get_day_reentry(
    db: AsyncSession,
    user_id: int,
    target_date: date,
) -> dict:
    daily_summary_join = and_(
        SummaryArtifact.day_id == Day.id,
        SummaryArtifact.kind == "daily",
    )
    previous_result = await db.execute(
        select(
            Day.date,
            Day.daily_note,
            SummaryArtifact.content,
        )
        .outerjoin(SummaryArtifact, daily_summary_join)
        .where(
            Day.user_id == user_id,
            Day.date < target_date,
            or_(
                func.length(func.trim(func.coalesce(Day.daily_note, ""))) > 0,
                func.length(
                    func.trim(func.coalesce(SummaryArtifact.content, ""))
                )
                > 0,
            ),
        )
        .order_by(Day.date.desc())
        .limit(1)
    )
    previous_row = previous_result.one_or_none()
    previous_trace = None
    if previous_row:
        previous_date, daily_note, summary = previous_row
        summary_preview = _preview(summary, 280)
        previous_trace = {
            "date": previous_date.isoformat(),
            "source": "summary" if summary_preview else "note",
            "excerpt": summary_preview or _preview(daily_note, 280),
        }

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= target_date,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
        .limit(3)
    )

    context_result = await db.execute(
        select(
            ContinuityContext.id,
            ContinuityContext.name,
            ContinuityContext.kind,
        )
        .join(
            DayContext,
            DayContext.context_id == ContinuityContext.id,
        )
        .join(Day, Day.id == DayContext.day_id)
        .where(
            Day.user_id == user_id,
            Day.date == target_date,
            ContinuityContext.user_id == user_id,
        )
        .order_by(ContinuityContext.name)
        .limit(4)
    )
    context_rows = context_result.all()
    context_ids = [context_id for context_id, _, _ in context_rows]
    activities: dict[int, dict] = {}
    if context_ids:
        ranked_days = (
            select(
                DayContext.context_id.label("context_id"),
                Day.id.label("day_id"),
                Day.date.label("activity_date"),
                Day.daily_note.label("daily_note"),
                func.row_number()
                .over(
                    partition_by=DayContext.context_id,
                    order_by=Day.date.desc(),
                )
                .label("position"),
            )
            .join(Day, Day.id == DayContext.day_id)
            .where(
                Day.user_id == user_id,
                Day.date < target_date,
                DayContext.context_id.in_(context_ids),
            )
            .subquery()
        )
        activity_result = await db.execute(
            select(
                ranked_days.c.context_id,
                ranked_days.c.activity_date,
                ranked_days.c.daily_note,
                SummaryArtifact.content,
            )
            .outerjoin(
                SummaryArtifact,
                and_(
                    SummaryArtifact.day_id == ranked_days.c.day_id,
                    SummaryArtifact.kind == "daily",
                ),
            )
            .where(ranked_days.c.position == 1)
        )
        for context_id, activity_date, daily_note, summary in (
            activity_result.all()
        ):
            summary_preview = _preview(summary, 180)
            note_preview = _preview(daily_note, 180)
            activities[context_id] = {
                "date": activity_date.isoformat(),
                "source": (
                    "summary"
                    if summary_preview
                    else "note" if note_preview else None
                ),
                "excerpt": summary_preview or note_preview,
            }

    return {
        "date": target_date.isoformat(),
        "previous_trace": previous_trace,
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
        "contexts": [
            {
                "id": context_id,
                "name": name,
                "kind": kind,
                "last_activity": activities.get(context_id),
            }
            for context_id, name, kind in context_rows
        ],
    }


async def get_week(
    db: AsyncSession,
    user_id: int,
    anchor_date: date,
) -> dict:
    week_start, week_end = _week_bounds(anchor_date)

    day_result = await db.execute(
        select(Day, DailyCheckin)
        .outerjoin(DailyCheckin, DailyCheckin.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
        )
        .order_by(Day.date)
    )
    day_rows = {
        day.date: (day, checkin)
        for day, checkin in day_result.all()
    }

    habit_result = await db.execute(
        select(Day.date, func.count(HabitLog.id))
        .join(HabitLog, HabitLog.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
        )
        .group_by(Day.date)
    )
    habit_counts = dict(habit_result.all())

    summary_result = await db.execute(
        select(Day.date, SummaryArtifact.content)
        .join(SummaryArtifact, SummaryArtifact.day_id == Day.id)
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
            SummaryArtifact.kind == "daily",
        )
    )
    summaries = dict(summary_result.all())

    context_result = await db.execute(
        select(
            Day.date,
            ContinuityContext.id,
            ContinuityContext.name,
            ContinuityContext.kind,
        )
        .join(DayContext, DayContext.day_id == Day.id)
        .join(
            ContinuityContext,
            ContinuityContext.id == DayContext.context_id,
        )
        .where(
            Day.user_id == user_id,
            Day.date >= week_start,
            Day.date <= week_end,
            ContinuityContext.user_id == user_id,
        )
        .order_by(Day.date, ContinuityContext.name)
    )
    contexts_by_date: dict[date, list[dict]] = {}
    for context_date, context_id, name, kind in context_result.all():
        contexts_by_date.setdefault(context_date, []).append(
            {"id": context_id, "name": name, "kind": kind}
        )

    thread_result = await db.execute(
        select(CarryForwardItem, Day.date)
        .join(Day, Day.id == CarryForwardItem.origin_day_id)
        .where(
            Day.user_id == user_id,
            Day.date <= week_end,
            CarryForwardItem.status == "open",
        )
        .order_by(Day.date, CarryForwardItem.created_at)
        .limit(20)
    )

    days = []
    for offset in range(7):
        current_date = week_start + timedelta(days=offset)
        day, checkin = day_rows.get(current_date, (None, None))
        daily_note = (day.daily_note or "").strip() if day else ""
        summary = (summaries.get(current_date) or "").strip()
        days.append(
            {
                "date": current_date.isoformat(),
                "has_entry": day is not None,
                "status": day.status if day else None,
                "note_preview": daily_note[:180],
                "summary_preview": summary[:240],
                "energy_level": (
                    checkin.energy_level if checkin else None
                ),
                "focus_quality": (
                    checkin.focus_quality if checkin else None
                ),
                "habit_completions": habit_counts.get(current_date, 0),
                "contexts": contexts_by_date.get(current_date, []),
            }
        )

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "totals": {
            "active_days": len(day_rows),
            "closed_days": sum(
                1 for day, _ in day_rows.values() if day.status == "closed"
            ),
            "habit_completions": sum(habit_counts.values()),
        },
        "days": days,
        "open_threads": [
            {
                "id": item.id,
                "origin_date": origin_date.isoformat(),
                "content": item.content,
            }
            for item, origin_date in thread_result.all()
        ],
    }


async def _lexical_search(
    db: AsyncSession,
    user_id: int,
    term: str,
    start_date: date,
    end_date: date,
    source: str = "all",
    limit: int = 20,
    context_id: int | None = None,
) -> dict:
    term = term.strip()
    if len(term) < 2:
        return _empty_search_payload(
            term, source, start_date, end_date, context_id
        )
    pattern = _like_pattern(term)
    results: list[dict] = []
    context_day_ids: list[int] | None = None

    if context_id is not None:
        context_exists = await db.scalar(
            select(ContinuityContext.id).where(
                ContinuityContext.id == context_id,
                ContinuityContext.user_id == user_id,
            )
        )
        if context_exists is None:
            raise ContextFilterNotFoundError(context_id)
        day_id_result = await db.execute(
            select(Day.id)
            .join(DayContext, DayContext.day_id == Day.id)
            .where(
                Day.user_id == user_id,
                Day.date >= start_date,
                Day.date <= end_date,
                DayContext.context_id == context_id,
            )
        )
        context_day_ids = list(day_id_result.scalars())

    if context_day_ids == []:
        return _empty_search_payload(
            term, source, start_date, end_date, context_id
        )

    if source in {"all", "notes"}:
        note_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            Day.daily_note.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            note_filters.append(Day.id.in_(context_day_ids))
        note_result = await db.execute(
            select(Day)
            .where(*note_filters)
            .order_by(Day.date.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "notes",
                "source_id": day.id,
                "date": day.date.isoformat(),
                "title": "Daily note",
                "excerpt": _excerpt(day.daily_note or "", term),
                "_sort_at": (
                    day.updated_at.isoformat() if day.updated_at else ""
                ),
            }
            for day in note_result.scalars()
        )

    if source in {"all", "conversation"}:
        conversation_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            ConversationEntry.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            conversation_filters.append(Day.id.in_(context_day_ids))
        conversation_result = await db.execute(
            select(ConversationEntry, Day.date)
            .join(Day, Day.id == ConversationEntry.day_id)
            .where(*conversation_filters)
            .order_by(Day.date.desc(), ConversationEntry.created_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "conversation",
                "source_id": entry.id,
                "date": entry_date.isoformat(),
                "title": "Conversation entry",
                "excerpt": _excerpt(entry.content, term),
                "_sort_at": entry.created_at.isoformat(),
            }
            for entry, entry_date in conversation_result.all()
        )

    if source in {"all", "summaries"}:
        summary_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            SummaryArtifact.kind == "daily",
            SummaryArtifact.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            summary_filters.append(Day.id.in_(context_day_ids))
        summary_result = await db.execute(
            select(SummaryArtifact, Day.date)
            .join(Day, Day.id == SummaryArtifact.day_id)
            .where(*summary_filters)
            .order_by(Day.date.desc(), SummaryArtifact.updated_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "summaries",
                "source_id": artifact.id,
                "date": summary_date.isoformat(),
                "title": "Daily summary",
                "excerpt": _excerpt(artifact.content, term),
                "_sort_at": artifact.updated_at.isoformat(),
            }
            for artifact, summary_date in summary_result.all()
        )

    if source in {"all", "threads"}:
        thread_filters = [
            Day.user_id == user_id,
            Day.date >= start_date,
            Day.date <= end_date,
            CarryForwardItem.content.ilike(pattern, escape="\\"),
        ]
        if context_day_ids is not None:
            thread_filters.append(Day.id.in_(context_day_ids))
        thread_result = await db.execute(
            select(CarryForwardItem, Day.date)
            .join(Day, Day.id == CarryForwardItem.origin_day_id)
            .where(*thread_filters)
            .order_by(Day.date.desc(), CarryForwardItem.created_at.desc())
            .limit(limit)
        )
        results.extend(
            {
                "source": "threads",
                "source_id": item.id,
                "date": origin_date.isoformat(),
                "title": "Follow-up",
                "excerpt": _excerpt(item.content, term),
                "status": item.status,
                "_sort_at": item.created_at.isoformat(),
            }
            for item, origin_date in thread_result.all()
        )

    if context_id is None and source in {"all", "weekly_reflections"}:
        reflection_result = await db.execute(
            select(WeeklyReflection)
            .where(
                WeeklyReflection.user_id == user_id,
                WeeklyReflection.week_start >= start_date,
                WeeklyReflection.week_start <= end_date,
                WeeklyReflection.content.ilike(pattern, escape="\\"),
            )
            .order_by(
                WeeklyReflection.week_start.desc(),
                WeeklyReflection.updated_at.desc(),
            )
            .limit(limit)
        )
        results.extend(
            {
                "source": "weekly_reflections",
                "source_id": reflection.id,
                "date": reflection.week_start.isoformat(),
                "title": "Weekly reflection",
                "excerpt": _excerpt(reflection.content, term),
                "_sort_at": reflection.updated_at.isoformat(),
            }
            for reflection in reflection_result.scalars()
        )

    results.sort(
        key=lambda item: (item["date"], item["_sort_at"]),
        reverse=True,
    )
    bounded = results[:limit]
    for item in bounded:
        item.pop("_sort_at", None)

    return {
        "query": term,
        "source": source,
        "context_id": context_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "results": bounded,
    }


_EMBEDDING_SOURCE_TITLES = {
    "notes": "Daily note",
    "conversation": "Conversation entry",
    "summaries": "Daily summary",
    "threads": "Follow-up",
    "weekly_reflections": "Weekly reflection",
}


def _current_embedding_source_exists():
    """Match derived rows to the source content currently in PostgreSQL.

    Embeddings are intentionally best-effort and may outlive a failed
    invalidation transaction.  Search must therefore validate the source at
    read time instead of trusting ``is_current`` alone.
    """

    embedding_content = func.trim(ContinuityEmbedding.content)
    return or_(
        and_(
            ContinuityEmbedding.source_type == "notes",
            select(Day.id)
            .where(
                Day.id == ContinuityEmbedding.source_id,
                Day.user_id == ContinuityEmbedding.user_id,
                Day.date == ContinuityEmbedding.source_date,
                func.length(func.trim(func.coalesce(Day.daily_note, ""))) > 0,
                func.trim(func.coalesce(Day.daily_note, ""))
                == embedding_content,
            )
            .exists(),
        ),
        and_(
            ContinuityEmbedding.source_type == "conversation",
            select(ConversationEntry.id)
            .join(Day, Day.id == ConversationEntry.day_id)
            .where(
                ConversationEntry.id == ContinuityEmbedding.source_id,
                Day.user_id == ContinuityEmbedding.user_id,
                Day.date == ContinuityEmbedding.source_date,
                func.length(func.trim(ConversationEntry.content)) > 0,
                func.trim(ConversationEntry.content) == embedding_content,
            )
            .exists(),
        ),
        and_(
            ContinuityEmbedding.source_type == "summaries",
            select(SummaryArtifact.id)
            .join(Day, Day.id == SummaryArtifact.day_id)
            .where(
                SummaryArtifact.id == ContinuityEmbedding.source_id,
                SummaryArtifact.kind == "daily",
                Day.user_id == ContinuityEmbedding.user_id,
                Day.date == ContinuityEmbedding.source_date,
                func.length(func.trim(SummaryArtifact.content)) > 0,
                func.trim(SummaryArtifact.content) == embedding_content,
            )
            .exists(),
        ),
        and_(
            ContinuityEmbedding.source_type == "threads",
            select(CarryForwardItem.id)
            .join(Day, Day.id == CarryForwardItem.origin_day_id)
            .where(
                CarryForwardItem.id == ContinuityEmbedding.source_id,
                Day.user_id == ContinuityEmbedding.user_id,
                Day.date == ContinuityEmbedding.source_date,
                func.length(func.trim(CarryForwardItem.content)) > 0,
                func.trim(CarryForwardItem.content) == embedding_content,
            )
            .exists(),
        ),
        and_(
            ContinuityEmbedding.source_type == "weekly_reflections",
            select(WeeklyReflection.id)
            .where(
                WeeklyReflection.id == ContinuityEmbedding.source_id,
                WeeklyReflection.user_id == ContinuityEmbedding.user_id,
                WeeklyReflection.week_start
                == ContinuityEmbedding.source_date,
                func.length(func.trim(WeeklyReflection.content)) > 0,
                func.trim(WeeklyReflection.content) == embedding_content,
            )
            .exists(),
        ),
    )


async def _semantic_search(
    db: AsyncSession,
    user_id: int,
    term: str,
    start_date: date,
    end_date: date,
    source: str,
    limit: int,
    context_id: int | None,
) -> list[dict]:
    term = term.strip()
    if len(term) < 2:
        return []

    context_day_ids: list[int] | None = None
    try:
        user_result = await db.execute(
            select(
                User.ai_processing_consent,
                User.ai_redaction_enabled,
            ).where(User.id == user_id)
        )
        user_row = user_result.one_or_none()
        if user_row is None or not user_row[0]:
            await _safe_search_rollback(db)
            return []
        redaction_enabled = bool(user_row[1])

        if context_id is not None:
            context_exists = await db.scalar(
                select(ContinuityContext.id).where(
                    ContinuityContext.id == context_id,
                    ContinuityContext.user_id == user_id,
                )
            )
            if context_exists is None:
                await _safe_search_rollback(db)
                raise ContextFilterNotFoundError(context_id)
            day_id_result = await db.execute(
                select(Day.id)
                .join(DayContext, DayContext.day_id == Day.id)
                .where(
                    Day.user_id == user_id,
                    Day.date >= start_date,
                    Day.date <= end_date,
                    DayContext.context_id == context_id,
                )
            )
            context_day_ids = list(day_id_result.scalars())
            if not context_day_ids:
                await _safe_search_rollback(db)
                return []

        # The provider request must not inherit this read transaction or its
        # pooled connection.
        await _safe_search_rollback(db)
    except ContextFilterNotFoundError:
        raise
    except Exception:
        await _safe_search_rollback(db)
        logger.warning("semantic continuity search user query failed")
        return []

    try:
        query_vector = await embedding_service.embed_text(
            term,
            input_type="query",
            redaction_enabled=redaction_enabled,
        )
    except Exception:
        logger.warning("semantic continuity search provider request failed")
        return []

    try:
        source_types = (
            tuple(_EMBEDDING_SOURCE_TITLES)
            if source == "all"
            else (source,)
        )
        distance = ContinuityEmbedding.embedding.cosine_distance(
            query_vector
        ).label("distance")
        filters = [
            ContinuityEmbedding.user_id == user_id,
            ContinuityEmbedding.source_type.in_(source_types),
            ContinuityEmbedding.source_date >= start_date,
            ContinuityEmbedding.source_date <= end_date,
            ContinuityEmbedding.is_current.is_(True),
            ContinuityEmbedding.embedding_model == settings.embedding_model,
            func.length(func.trim(ContinuityEmbedding.content)) > 0,
            _current_embedding_source_exists(),
        ]
        if context_day_ids is not None:
            filters.append(ContinuityEmbedding.day_id.in_(context_day_ids))
        candidate_limit = min(max(limit * 4, limit), 200)
        scan_mode = await _enable_iterative_hnsw_scan(db)
        if scan_mode is None:
            logger.warning("semantic continuity exact scan setup failed")
            return []
        result = await db.execute(
            select(ContinuityEmbedding, distance)
            .where(*filters)
            .order_by(distance)
            .limit(candidate_limit)
        )
        rows = result.all()

        thread_ids = [
            embedding.source_id
            for embedding, _ in rows
            if embedding.source_type == "threads"
        ]
        thread_statuses: dict[int, str] = {}
        if thread_ids:
            thread_result = await db.execute(
                select(CarryForwardItem.id, CarryForwardItem.status)
                .join(Day, Day.id == CarryForwardItem.origin_day_id)
                .where(
                    CarryForwardItem.id.in_(thread_ids),
                    Day.user_id == user_id,
                )
            )
            thread_statuses = dict(thread_result.all())

        semantic_results: list[dict] = []
        for embedding, rank in rows:
            source_title = _EMBEDDING_SOURCE_TITLES.get(
                embedding.source_type
            )
            source_date = embedding.source_date
            if source_title is None or source_date is None:
                continue
            result_item = {
                "source": embedding.source_type,
                "source_id": embedding.source_id,
                "date": source_date.isoformat(),
                "title": source_title,
                "excerpt": _excerpt(embedding.content, term),
                "_semantic_rank": float(rank),
                "_sort_at": (
                    embedding.updated_at.isoformat()
                    if embedding.updated_at
                    else ""
                ),
            }
            if embedding.source_type == "threads":
                status = thread_statuses.get(embedding.source_id)
                if status is None:
                    continue
                result_item["status"] = status
            semantic_results.append(result_item)
        await _safe_search_rollback(db)
        return semantic_results[:limit]
    except SQLAlchemyError:
        await _safe_search_rollback(db)
        logger.warning("semantic continuity search database query failed")
        return []
    except Exception:
        await _safe_search_rollback(db)
        logger.warning("semantic continuity search result mapping failed")
        return []


async def search(
    db: AsyncSession,
    user_id: int,
    term: str,
    start_date: date,
    end_date: date,
    source: str = "all",
    limit: int = 20,
    context_id: int | None = None,
) -> dict:
    """Search semantic matches first and retain exact lexical fallback."""

    term = term.strip()
    if len(term) < 2:
        return _empty_search_payload(
            term, source, start_date, end_date, context_id
        )

    semantic_results = await _semantic_search(
        db,
        user_id,
        term,
        start_date,
        end_date,
        source,
        limit,
        context_id,
    )
    lexical_payload = await _lexical_search(
        db,
        user_id,
        term,
        start_date,
        end_date,
        source,
        limit,
        context_id,
    )
    if not semantic_results:
        return lexical_payload

    return {
        **lexical_payload,
        "results": _merge_search_results(
            semantic_results,
            lexical_payload["results"],
            limit,
        ),
    }


def _merge_search_results(
    semantic_results: list[dict],
    lexical_results: list[dict],
    limit: int,
) -> list[dict]:
    """Merge ordered semantic and lexical rows without duplicate sources."""

    merged: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for item in semantic_results:
        key = (item["source"], item["source_id"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    for item in lexical_results:
        key = (item["source"], item["source_id"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    bounded = merged[:limit]
    for item in bounded:
        item.pop("_semantic_rank", None)
        item.pop("_sort_at", None)
    return bounded

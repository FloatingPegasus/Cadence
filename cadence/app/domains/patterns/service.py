from collections import Counter
from datetime import date, timedelta
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...persistence.models.continuity_context import ContinuityContext
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.daily_checkin import DailyCheckin
from ...persistence.models.day import Day
from ...persistence.models.day_context import DayContext
from ...persistence.models.habit_log import HabitLog


CHECKIN_FIELDS = (
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


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


async def get_patterns(
    db: AsyncSession,
    user_id: int,
    anchor_date: date,
    weeks: int,
) -> dict:
    end_week = _week_start(anchor_date)
    start_week = end_week - timedelta(weeks=weeks - 1)
    end_date = end_week + timedelta(days=6)

    days = list(
        (
            await db.scalars(
                select(Day)
                .where(
                    Day.user_id == user_id,
                    Day.date >= start_week,
                    Day.date <= end_date,
                )
                .order_by(Day.date)
            )
        ).all()
    )
    day_ids = [day.id for day in days]

    checkins: dict[int, DailyCheckin] = {}
    conversation_days: set[int] = set()
    completion_counts: dict[int, int] = {}
    context_counts: dict[int, int] = {}
    context_rows: list[tuple[int, str, date]] = []
    if day_ids:
        checkins = {
            checkin.day_id: checkin
            for checkin in (
                await db.scalars(
                    select(DailyCheckin).where(
                        DailyCheckin.day_id.in_(day_ids)
                    )
                )
            ).all()
        }
        conversation_days = set(
            (
                await db.scalars(
                    select(ConversationEntry.day_id)
                    .where(ConversationEntry.day_id.in_(day_ids))
                    .distinct()
                )
            ).all()
        )
        completion_counts = dict(
            (
                await db.execute(
                    select(HabitLog.day_id, func.count(HabitLog.id))
                    .where(HabitLog.day_id.in_(day_ids))
                    .group_by(HabitLog.day_id)
                )
            ).all()
        )
        context_counts = dict(
            (
                await db.execute(
                    select(DayContext.day_id, func.count(DayContext.context_id))
                    .where(DayContext.day_id.in_(day_ids))
                    .group_by(DayContext.day_id)
                )
            ).all()
        )
        context_rows = list(
            (
                await db.execute(
                    select(
                        ContinuityContext.id,
                        ContinuityContext.name,
                        Day.date,
                    )
                    .join(
                        DayContext,
                        DayContext.context_id == ContinuityContext.id,
                    )
                    .join(Day, Day.id == DayContext.day_id)
                    .where(
                        ContinuityContext.user_id == user_id,
                        Day.id.in_(day_ids),
                    )
                    .order_by(Day.date)
                )
            ).all()
        )

    def has_checkin(day_id: int) -> bool:
        checkin = checkins.get(day_id)
        return bool(
            checkin
            and any(getattr(checkin, field) is not None for field in CHECKIN_FIELDS)
        )

    meaningful = [
        day
        for day in days
        if (day.daily_note or "").strip()
        or day.status == "closed"
        or has_checkin(day.id)
        or day.id in conversation_days
        or completion_counts.get(day.id, 0)
        or context_counts.get(day.id, 0)
    ]
    meaningful_dates = {day.date for day in meaningful}

    buckets = []
    active_counts = []
    for offset in range(weeks):
        bucket_start = start_week + timedelta(weeks=offset)
        bucket_end = bucket_start + timedelta(days=6)
        bucket_days = [
            day
            for day in meaningful
            if bucket_start <= day.date <= bucket_end
        ]
        energy_values = [
            checkins[day.id].energy_level
            for day in bucket_days
            if day.id in checkins
            and checkins[day.id].energy_level is not None
        ]
        focus_values = [
            checkins[day.id].focus_quality
            for day in bucket_days
            if day.id in checkins
            and checkins[day.id].focus_quality is not None
        ]
        active_counts.append(len(bucket_days))
        buckets.append(
            {
                "week_start": bucket_start.isoformat(),
                "week_end": bucket_end.isoformat(),
                "active_days": len(bucket_days),
                "habit_completions": sum(
                    completion_counts.get(day.id, 0)
                    for day in bucket_days
                ),
                "average_energy": (
                    round(sum(energy_values) / len(energy_values), 1)
                    if energy_values
                    else None
                ),
                "average_focus": (
                    round(sum(focus_values) / len(focus_values), 1)
                    if focus_values
                    else None
                ),
            }
        )

    observations = []
    active_weeks = sum(count > 0 for count in active_counts)
    observations.append(
        {
            "kind": "rhythm",
            "title": "Recorded rhythm",
            "body": (
                f"Activity appears in {active_weeks} of {weeks} weeks, "
                f"with a median of {median(active_counts):g} recorded "
                "days per week."
            ),
            "evidence": {
                "active_weeks": active_weeks,
                "weeks": weeks,
                "median_active_days": median(active_counts),
            },
        }
    )

    context_day_counts = Counter(
        context_id
        for context_id, _name, day_date in context_rows
        if day_date in meaningful_dates
    )
    if context_day_counts:
        top_context_id, top_days = context_day_counts.most_common(1)[0]
        top_name = next(
            name
            for context_id, name, _date in context_rows
            if context_id == top_context_id
        )
        context_weeks = {
            _week_start(day_date)
            for context_id, _name, day_date in context_rows
            if context_id == top_context_id
        }
        observations.append(
            {
                "kind": "context",
                "title": "Recurring context",
                "body": (
                    f"{top_name} appears on {top_days} recorded days "
                    f"across {len(context_weeks)} weeks."
                ),
                "evidence": {
                    "context_id": top_context_id,
                    "days": top_days,
                    "weeks": len(context_weeks),
                },
            }
        )

    gaps = [
        (current.date - previous.date).days - 1
        for previous, current in zip(meaningful, meaningful[1:])
        if (current.date - previous.date).days > 2
    ]
    if gaps:
        observations.append(
            {
                "kind": "return",
                "title": "Returns after gaps",
                "body": (
                    f"The record contains {len(gaps)} "
                    f"{'return' if len(gaps) == 1 else 'returns'} after "
                    "gaps of two or more days."
                ),
                "evidence": {
                    "returns": len(gaps),
                    "longest_gap_days": max(gaps),
                },
            }
        )

    return {
        "start_date": start_week.isoformat(),
        "end_date": end_date.isoformat(),
        "weeks": weeks,
        "totals": {
            "recorded_days": len(meaningful),
            "active_weeks": active_weeks,
        },
        "weekly": buckets,
        "observations": observations,
        "interpretation": (
            "Patterns describe recorded data only. They are not scores, "
            "predictions, or judgments about unrecorded time."
        ),
    }

from datetime import date, timedelta
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..days import service as days_service
from ...config import settings
from ...persistence.models.conversation_entry import ConversationEntry
from ...persistence.models.day import Day
from ...persistence.models.user import User
from ...services import ai as ai_service
from .context import build_context

REPLY_RULES = (
    "You are Cadence, a steady companion inside someone's daily log. "
    "They just wrote the log below. Reply in two to four sentences of plain text. "
    "Use their own words where you can. "
    "Give one concrete next step that fits what they wrote and what you know "
    "about them. "
    "No praise, no cheerleading, no emoji, and no diagnosis or labels for how "
    "they feel. "
    "If the writing shows distress, slow down: say plainly what you notice and "
    "offer one grounding step, such as three slow breaths or naming five things "
    "they can see. "
    "Do not invent facts that are not in the log or the context."
)

CRISIS_PHRASES = (
    r"kill(?:ing)? myself",
    r"end(?:ing)? my (?:own )?life",
    r"end it all",
    r"take my (?:own )?life",
    r"suicid(?:e|al)",
    r"(?:want|wanna) to die",
    r"wish i (?:was|were) dead",
    r"better off dead",
    r"(?:don't|dont|do not) want to (?:live|be alive)",
    r"no reason to live",
    r"self[- ]?harm",
    r"(?:hurt|hurting|cut|cutting) myself",
)
CRISIS_PATTERN = re.compile(
    r"\b(?:" + "|".join(CRISIS_PHRASES) + r")\b", re.IGNORECASE
)

LIMIT_NOTICE = "That's all the replies for today. Your log is saved."
FAILED_NOTICE = "Cadence couldn't reply just now. Your log is saved."


def crisis_line(text: str) -> str | None:
    if settings.crisis_resources and CRISIS_PATTERN.search(text.replace("’", "'")):
        return settings.crisis_resources
    return None


def _join(*parts: str | None) -> str | None:
    return "\n\n".join(part for part in parts if part) or None


async def replies_in_last_day(db: AsyncSession, user_id: int) -> int:
    return await db.scalar(
        select(func.count(ConversationEntry.id))
        .join(Day, Day.id == ConversationEntry.day_id)
        .where(
            Day.user_id == user_id,
            ConversationEntry.role == "assistant",
            ConversationEntry.created_at >= func.now() - timedelta(days=1),
        )
    )


async def add_log(
    db: AsyncSession,
    user: User,
    target_date: date,
    content: str,
    hour: int | None,
    *,
    reply: bool,
) -> dict:
    user_id = user.id
    can_reply = (
        reply
        and settings.ai_enabled
        and not user.is_guest
        and user.ai_processing_consent
    )
    log = await days_service.add_log(db, user_id, target_date, content, hour)
    crisis = crisis_line(log["content"])
    result = {"log": log, "reply": None, "notice": crisis}
    if not can_reply:
        return result
    if await replies_in_last_day(db, user_id) >= settings.ai_daily_reply_limit:
        result["notice"] = _join(LIMIT_NOTICE, crisis)
        return result

    context = await build_context(
        db, user_id, target_date, log["content"], exclude_id=log["id"]
    )
    messages = [{"role": "system", "content": REPLY_RULES}]
    if context:
        messages.append(
            {"role": "system", "content": f"What you know about them:\n\n{context}"}
        )
    messages.append({"role": "user", "content": log["content"]})
    try:
        response = await ai_service.chat_with_fallback(
            db,
            task="reply",
            messages=messages,
            max_tokens=300,
            temperature=0.4,
            user_id=user_id,
        )
    except (
        ai_service.AIConsentRequiredError,
        ai_service.AIConfigurationError,
        ai_service.AIProvidersExhaustedError,
    ):
        result["notice"] = _join(FAILED_NOTICE, crisis)
        return result

    text = _join(response["content"].strip(), crisis)
    result["reply"] = await days_service.add_log(
        db, user_id, target_date, text, hour, role="assistant"
    )
    result["notice"] = None
    return result

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


CONTINUITY_ADVISORY_LOCK_NAMESPACE = 0x43414445


async def acquire_continuity_lock(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        select(
            func.pg_advisory_xact_lock(
                CONTINUITY_ADVISORY_LOCK_NAMESPACE,
                user_id,
            )
        )
    )

from __future__ import annotations

import asyncio
import bcrypt
from datetime import date, datetime, timedelta
import sys
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path

if __package__ == "cadence.tests.integration":
    from ..bootstrap import configure_test_environment
    from .support import disposable_database, integration_enabled
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap import configure_test_environment
    from integration.support import disposable_database, integration_enabled

configure_test_environment()

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cadence.app.config import settings
from cadence.app.domains.continuity import service as continuity_service
from cadence.app.persistence.models.continuity_context import ContinuityContext
from cadence.app.persistence.models.continuity_embedding import ContinuityEmbedding
from cadence.app.persistence.models.day import Day
from cadence.app.persistence.models.day_context import DayContext
from cadence.app.persistence.models.user import User
from cadence.app.services import embeddings


def _vector(axis: int, value: float = 1.0) -> list[float]:
    vector = [0.0] * 1024
    vector[axis] = value
    return vector


@unittest.skipUnless(
    integration_enabled(),
    "set CADENCE_RUN_INTEGRATION=1 to run PostgreSQL integration tests",
)
class PgvectorIntegrationTests(unittest.TestCase):
    def test_vector_search_filters_cas_purge_and_backfill(self) -> None:
        async def run(database):
            engine = database.async_engine()
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            original_ai_enabled = settings.ai_enabled
            original_embedding_enabled = settings.embedding_enabled
            try:
                async with session_factory() as db:
                    user = User(
                        username="pgvector-integration-user",
                        email="pgvector-integration@example.com",
                        hashed_password=bcrypt.hashpw(
                            b"test-password", bcrypt.gensalt()
                        ).decode(),
                        is_verified=True,
                        ai_processing_consent=True,
                    )
                    other_user = User(
                        username="pgvector-other-user",
                        email="pgvector-other@example.com",
                        hashed_password=bcrypt.hashpw(
                            b"test-password", bcrypt.gensalt()
                        ).decode(),
                        is_verified=True,
                        ai_processing_consent=True,
                    )
                    db.add_all([user, other_user])
                    await db.flush()
                    context = ContinuityContext(
                        user_id=user.id,
                        name="Integration context",
                        kind="project",
                    )
                    db.add(context)
                    await db.flush()
                    target_day = Day(
                        user_id=user.id,
                        date=date(2026, 8, 15),
                        daily_note="target vector source",
                    )
                    second_day = Day(
                        user_id=user.id,
                        date=date(2026, 8, 16),
                        daily_note="second vector source",
                    )
                    old_day = Day(
                        user_id=user.id,
                        date=date(2025, 1, 1),
                        daily_note="outside date source",
                    )
                    other_day = Day(
                        user_id=other_user.id,
                        date=date(2026, 8, 15),
                        daily_note="other user source",
                    )
                    db.add_all([target_day, second_day, old_day, other_day])
                    await db.flush()
                    db.add(DayContext(day_id=target_day.id, context_id=context.id))
                    db.add_all(
                        [
                            ContinuityEmbedding(
                                user_id=user.id,
                                source_type="notes",
                                source_id=target_day.id,
                                day_id=target_day.id,
                                source_date=target_day.date,
                                content=target_day.daily_note,
                                content_hash=embeddings._content_hash(
                                    target_day.daily_note
                                ),
                                embedding_model=settings.embedding_model,
                                embedding=_vector(0),
                                is_current=True,
                            ),
                            ContinuityEmbedding(
                                user_id=user.id,
                                source_type="notes",
                                source_id=second_day.id,
                                day_id=second_day.id,
                                source_date=second_day.date,
                                content=second_day.daily_note,
                                content_hash=embeddings._content_hash(
                                    second_day.daily_note
                                ),
                                embedding_model=settings.embedding_model,
                                embedding=_vector(1),
                                is_current=True,
                            ),
                            ContinuityEmbedding(
                                user_id=other_user.id,
                                source_type="notes",
                                source_id=other_day.id,
                                day_id=other_day.id,
                                source_date=other_day.date,
                                content=other_day.daily_note,
                                content_hash=embeddings._content_hash(
                                    other_day.daily_note
                                ),
                                embedding_model=settings.embedding_model,
                                embedding=_vector(0),
                                is_current=True,
                            ),
                        ]
                    )
                    await db.commit()
                    user_id = user.id
                    context_id = context.id
                    target_day_id = target_day.id
                    target_day_content = target_day.daily_note
                    second_day_id = second_day.id
                    second_day_content = second_day.daily_note
                    old_day_id = old_day.id
                    old_day_date = old_day.date
                    query_vector = _vector(0)
                    distance = ContinuityEmbedding.embedding.cosine_distance(
                        query_vector
                    )
                    ordered = list(
                        (
                            await db.execute(
                                select(ContinuityEmbedding.source_id)
                                .where(
                                    ContinuityEmbedding.user_id == user_id,
                                    ContinuityEmbedding.is_current.is_(True),
                                )
                                .order_by(distance)
                            )
                        ).scalars()
                    )
                    self.assertEqual(
                        ordered[:2], [target_day_id, second_day_id]
                    )

                    with patch.object(
                        continuity_service.embedding_service,
                        "embed_text",
                        new=AsyncMock(return_value=query_vector),
                    ):
                        filtered = await continuity_service._semantic_search(
                            db,
                            user_id,
                            "target",
                            date(2026, 8, 1),
                            date(2026, 8, 31),
                            "notes",
                            20,
                            context_id,
                        )
                    self.assertEqual(
                        [(item["source"], item["source_id"]) for item in filtered],
                        [("notes", target_day_id)],
                    )

                    stale = ContinuityEmbedding(
                        user_id=user_id,
                        source_type="notes",
                        source_id=old_day_id,
                        day_id=old_day_id,
                        source_date=old_day_date,
                        content="old source content",
                        content_hash=embeddings._content_hash(
                            "old source content"
                        ),
                        embedding_model=settings.embedding_model,
                        embedding=_vector(2),
                        is_current=False,
                    )
                    stale_hash = stale.content_hash
                    db.add(stale)
                    await db.commit()
                    stale_id = stale.id
                    await db.execute(
                        update(Day)
                        .where(Day.id == old_day_id)
                        .values(daily_note="new source content")
                    )
                    await db.commit()
                    self.assertFalse(
                        await embeddings._activate_embedding(
                            db,
                            user_id=user_id,
                            source_type="notes",
                            source_id=old_day_id,
                            content="old source content",
                            content_hash=stale_hash,
                            placeholder_id=stale_id,
                            day_id=old_day_id,
                            source_date=old_day_date,
                            vector=_vector(0),
                        )
                    )
                    stale_row = await db.scalar(
                        select(ContinuityEmbedding).where(
                            ContinuityEmbedding.id == stale_id
                        )
                    )
                    self.assertFalse(stale_row.is_current)
                    self.assertEqual(stale_row.embedding[2], 1.0)

                    await db.execute(
                        update(Day)
                        .where(Day.id == second_day_id)
                        .values(daily_note="")
                    )
                    await db.commit()
                    self.assertTrue(
                        await embeddings._clear_source_embedding(
                            db,
                            user_id=user_id,
                            source_type="notes",
                            source_id=second_day_id,
                            content="",
                        )
                    )
                    self.assertIsNone(
                        await db.scalar(
                            select(ContinuityEmbedding).where(
                                ContinuityEmbedding.user_id == user_id,
                                ContinuityEmbedding.source_id == second_day_id,
                            )
                        )
                    )
                    await db.execute(
                        update(Day)
                        .where(Day.id == second_day_id)
                        .values(daily_note=second_day_content)
                    )
                    await db.commit()

                    await embeddings.purge_user_embeddings(db, user_id)
                    await db.commit()
                    remaining = await db.scalar(
                        select(func.count(ContinuityEmbedding.id)).where(
                            ContinuityEmbedding.user_id == user_id
                        )
                    )
                    self.assertEqual(remaining, 0)

                    settings.ai_enabled = True
                    settings.embedding_enabled = True
                    with patch.object(
                        embeddings,
                        "embed_text",
                        new=AsyncMock(return_value=_vector(0)),
                    ):
                        result = await embeddings.backfill_embeddings(
                            db,
                            user_id=user_id,
                            batch_size=20,
                        )
                    self.assertGreaterEqual(result["refreshed"], 3)
                    self.assertEqual(result["failed"], 0)
                    refreshed = await db.scalar(
                        select(ContinuityEmbedding).where(
                            ContinuityEmbedding.user_id == user_id,
                            ContinuityEmbedding.source_id == target_day_id,
                        )
                    )
                    self.assertTrue(refreshed.is_current)
                    self.assertEqual(
                        refreshed.content_hash,
                        embeddings._content_hash(target_day_content),
                    )
            finally:
                settings.ai_enabled = original_ai_enabled
                settings.embedding_enabled = original_embedding_enabled
                await engine.dispose()

        with disposable_database() as database:
            database.run_alembic("upgrade", "head")
            asyncio.run(run(database))

    def test_purge_recreate_same_hash_cannot_activate_old_claim(self) -> None:
        async def run(database):
            engine = database.async_engine()
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            try:
                async with session_factory() as db:
                    user = User(
                        username="pgvector-cas-user",
                        email="pgvector-cas@example.com",
                        hashed_password=bcrypt.hashpw(
                            b"test-password", bcrypt.gensalt()
                        ).decode(),
                        is_verified=True,
                        ai_processing_consent=True,
                    )
                    db.add(user)
                    await db.flush()
                    day = Day(
                        user_id=user.id,
                        date=date(2026, 8, 20),
                        daily_note="same content after purge",
                    )
                    db.add(day)
                    await db.commit()
                    user_id = user.id
                    day_id = day.id
                    source_date = day.date

                content = "same content after purge"
                content_hash = embeddings._content_hash(content)
                async with session_factory() as old_db:
                    old_claim = await embeddings._prepare_placeholder(
                        old_db,
                        user_id=user_id,
                        source_type="notes",
                        source_id=day_id,
                        content=content,
                        content_hash=content_hash,
                        day_id=day_id,
                        source_date=source_date,
                        return_id=True,
                    )

                async with session_factory() as purge_db:
                    await embeddings.purge_user_embeddings(purge_db, user_id)
                    await purge_db.commit()

                async with session_factory() as replacement_db:
                    replacement_claim = await embeddings._prepare_placeholder(
                        replacement_db,
                        user_id=user_id,
                        source_type="notes",
                        source_id=day_id,
                        content=content,
                        content_hash=content_hash,
                        day_id=day_id,
                        source_date=source_date,
                        return_id=True,
                    )

                old_id = old_claim[2]
                replacement_id = replacement_claim[2]
                self.assertTrue(old_claim[0] and old_claim[1])
                self.assertTrue(
                    replacement_claim[0] and replacement_claim[1]
                )
                self.assertNotEqual(old_id, replacement_id)

                async with session_factory() as old_db:
                    self.assertFalse(
                        await embeddings._activate_embedding(
                            old_db,
                            user_id=user_id,
                            source_type="notes",
                            source_id=day_id,
                            content=content,
                            content_hash=content_hash,
                            placeholder_id=old_id,
                            day_id=day_id,
                            source_date=source_date,
                            vector=_vector(0),
                        )
                    )

                async with session_factory() as replacement_db:
                    self.assertTrue(
                        await embeddings._activate_embedding(
                            replacement_db,
                            user_id=user_id,
                            source_type="notes",
                            source_id=day_id,
                            content=content,
                            content_hash=content_hash,
                            placeholder_id=replacement_id,
                            day_id=day_id,
                            source_date=source_date,
                            vector=_vector(1),
                        )
                    )
                    row = await replacement_db.scalar(
                        select(ContinuityEmbedding).where(
                            ContinuityEmbedding.user_id == user_id,
                            ContinuityEmbedding.source_id == day_id,
                        )
                    )
                    self.assertEqual(row.id, replacement_id)
                    self.assertTrue(row.is_current)
                    self.assertEqual(row.embedding[1], 1.0)
            finally:
                await engine.dispose()

        with disposable_database() as database:
            database.run_alembic("upgrade", "head")
            asyncio.run(run(database))

    def test_backfill_finds_stale_hash_after_first_scan_page(self) -> None:
        async def run(database):
            engine = database.async_engine()
            session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            original_ai_enabled = settings.ai_enabled
            original_embedding_enabled = settings.embedding_enabled
            try:
                async with session_factory() as db:
                    user = User(
                        username="pgvector-backfill-user",
                        email="pgvector-backfill@example.com",
                        hashed_password=bcrypt.hashpw(
                            b"test-password", bcrypt.gensalt()
                        ).decode(),
                        is_verified=True,
                        ai_processing_consent=True,
                    )
                    db.add(user)
                    await db.flush()
                    days = [
                        Day(
                            user_id=user.id,
                            date=date(2024, 1, 1) + timedelta(days=index),
                            daily_note=f"backfill source {index}",
                        )
                        for index in range(401)
                    ]
                    db.add_all(days)
                    await db.flush()
                    db.add_all(
                        [
                            ContinuityEmbedding(
                                user_id=user.id,
                                source_type="notes",
                                source_id=day.id,
                                day_id=day.id,
                                source_date=day.date,
                                content=day.daily_note,
                                content_hash=(
                                    "0" * 64
                                    if index == 400
                                    else embeddings._content_hash(
                                        day.daily_note
                                    )
                                ),
                                embedding_model=settings.embedding_model,
                                embedding=_vector(0),
                                is_current=True,
                                updated_at=(
                                    datetime(2020, 1, 1)
                                    if index == 400
                                    else datetime(2026, 1, 1)
                                ),
                            )
                            for index, day in enumerate(days)
                        ]
                    )
                    await db.commit()
                    user_id = user.id
                    stale_id = days[-1].id

                    settings.ai_enabled = True
                    settings.embedding_enabled = True
                    with patch.object(
                        embeddings,
                        "embed_text",
                        new=AsyncMock(return_value=_vector(1)),
                    ):
                        result = await embeddings.backfill_embeddings(
                            db,
                            user_id=user_id,
                            batch_size=1,
                        )
                    stale = await db.scalar(
                        select(ContinuityEmbedding).where(
                            ContinuityEmbedding.user_id == user_id,
                            ContinuityEmbedding.source_id == stale_id,
                        )
                    )
                    self.assertEqual(
                        result,
                        {"attempted": 1, "refreshed": 1, "failed": 0},
                    )
                    self.assertTrue(stale.is_current)
                    self.assertEqual(stale.embedding[1], 1.0)
            finally:
                settings.ai_enabled = original_ai_enabled
                settings.embedding_enabled = original_embedding_enabled
                await engine.dispose()

        with disposable_database() as database:
            database.run_alembic("upgrade", "head")
            asyncio.run(run(database))


if __name__ == "__main__":
    unittest.main()

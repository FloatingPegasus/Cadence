from __future__ import annotations

import asyncio
import bcrypt
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

if __package__ == "cadence.tests.integration":
    from ..bootstrap import configure_test_environment
    from .support import disposable_database, integration_enabled
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap import configure_test_environment
    from integration.support import disposable_database, integration_enabled

configure_test_environment()

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cadence.app.persistence.models.continuity_embedding import ContinuityEmbedding
from cadence.app.persistence.models.day import Day
from cadence.app.persistence.models.user import User
from cadence.app.services.backups import create_backup, restore_database


@unittest.skipUnless(
    integration_enabled(),
    "set CADENCE_RUN_INTEGRATION=1 to run PostgreSQL integration tests",
)
class BackupIntegrationTests(unittest.TestCase):
    def test_pg_dump_restore_preserves_data_extensions_and_indexes(self) -> None:
        async def seed(engine) -> tuple[int, str]:
            async with async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )() as db:
                user = User(
                    username="backup-integration-user",
                    email="backup-integration@example.com",
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
                    date=date(2026, 8, 15),
                    daily_note="backup round trip note",
                )
                db.add(day)
                await db.flush()
                db.add(
                    ContinuityEmbedding(
                        user_id=user.id,
                        source_type="notes",
                        source_id=day.id,
                        day_id=day.id,
                        source_date=day.date,
                        content=day.daily_note,
                        content_hash="b" * 64,
                        embedding_model="integration-model",
                        embedding=[1.0] + [0.0] * 1023,
                        is_current=True,
                    )
                )
                await db.commit()
                return user.id, day.daily_note

        async def inspect(engine, user_id: int, content: str) -> None:
            async with engine.connect() as connection:
                self.assertEqual(
                    set(
                        (
                            await connection.execute(
                                text(
                                    "SELECT extname FROM pg_extension "
                                    "WHERE extname IN ('vector', 'pg_trgm')"
                                )
                            )
                        ).scalars()
                    ),
                    {"vector", "pg_trgm"},
                )
                indexes = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE schemaname = current_schema()"
                            )
                        )
                    ).scalars()
                )
                self.assertTrue(
                    {
                        "ix_continuity_embeddings_embedding_hnsw",
                        "ix_days_daily_note_trgm",
                        "ix_conversation_entries_content_trgm",
                        "ix_carry_forward_items_content_trgm",
                        "ix_summary_artifacts_content_trgm",
                        "ix_weekly_reflections_content_trgm",
                    }.issubset(indexes)
                )
                hnsw_definition = await connection.scalar(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE indexname = 'ix_continuity_embeddings_embedding_hnsw'"
                    )
                )
                trgm_definition = await connection.scalar(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE indexname = 'ix_days_daily_note_trgm'"
                    )
                )
                self.assertIn("hnsw", hnsw_definition.casefold())
                self.assertIn("vector_cosine_ops", hnsw_definition.casefold())
                self.assertIn("gin", trgm_definition.casefold())
                self.assertIn("gin_trgm_ops", trgm_definition.casefold())

            async with async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )() as db:
                row = await db.scalar(
                    select(Day).where(
                        Day.user_id == user_id,
                        Day.daily_note == content,
                    )
                )
                self.assertIsNotNone(row)
                embedding = await db.scalar(
                    select(ContinuityEmbedding).where(
                        ContinuityEmbedding.user_id == user_id,
                        ContinuityEmbedding.source_id == row.id,
                    )
                )
                self.assertEqual(embedding.embedding[0], 1.0)
                self.assertEqual(embedding.embedding_model, "integration-model")

        async def replace_target_indexes_with_decoys(engine) -> None:
            decoys = {
                "ix_continuity_embeddings_embedding_hnsw": (
                    "continuity_embeddings"
                ),
                "ix_days_daily_note_trgm": "days",
                "ix_conversation_entries_content_trgm": "conversation_entries",
                "ix_carry_forward_items_content_trgm": "carry_forward_items",
                "ix_summary_artifacts_content_trgm": "summary_artifacts",
                "ix_weekly_reflections_content_trgm": "weekly_reflections",
            }
            async with engine.begin() as connection:
                for index_name in decoys:
                    await connection.execute(
                        text(f'DROP INDEX "{index_name}"')
                    )
                for index_name, table_name in decoys.items():
                    await connection.execute(
                        text(
                            f'CREATE INDEX "{index_name}" '
                            f'ON "{table_name}" (id)'
                        )
                    )

        with (
            disposable_database(require_pg_tools=True) as source,
            disposable_database(require_pg_tools=True) as target,
            tempfile.TemporaryDirectory(
                prefix="cadence-integration-backup-"
            ) as directory,
        ):
            source.run_alembic("upgrade", "head")
            target.run_alembic("upgrade", "head")
            source_engine = source.async_engine()
            target_engine = target.async_engine()
            try:
                user_id, content = asyncio.run(seed(source_engine))
                asyncio.run(replace_target_indexes_with_decoys(target_engine))
                with tempfile.TemporaryDirectory(
                    prefix="cadence-target-backup-"
                ) as target_backup_directory:
                    backup = create_backup(
                        source.url.render_as_string(hide_password=False),
                        Path(directory),
                        keep=2,
                    )
                    restore_database(
                        backup.path,
                        target.url.render_as_string(hide_password=False),
                        Path(target_backup_directory),
                        keep=2,
                    )
                asyncio.run(inspect(target_engine, user_id, content))
            finally:
                asyncio.run(source_engine.dispose())
                asyncio.run(target_engine.dispose())


if __name__ == "__main__":
    unittest.main()

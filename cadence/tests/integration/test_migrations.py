from __future__ import annotations

import asyncio
import bcrypt
import unittest
from datetime import date
import sys
from pathlib import Path

if __package__ == "cadence.tests.integration":
    from ..bootstrap import configure_test_environment
    from .support import disposable_database, integration_enabled
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap import configure_test_environment
    from integration.support import disposable_database, integration_enabled

configure_test_environment()

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cadence.app.persistence.models.day import Day
from cadence.app.persistence.models.user import User
from cadence.app.web.routes.auth import _create_token
from cadence.app.extensions import get_db


@unittest.skipUnless(
    integration_enabled(),
    "set CADENCE_RUN_INTEGRATION=1 to run PostgreSQL integration tests",
)
class MigrationIntegrationTests(unittest.TestCase):
    def test_fresh_database_migrates_round_trip_and_serves_api(self) -> None:
        async def seed_and_inspect(engine) -> int:
            async with engine.connect() as connection:
                extensions = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT extname FROM pg_extension "
                                "WHERE extname IN ('vector', 'pg_trgm')"
                            )
                        )
                    ).scalars()
                )
                self.assertEqual(extensions, {"vector", "pg_trgm"})
                table_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE schemaname = current_schema() "
                        "AND tablename IN ("
                        "'users', 'days', 'continuity_embeddings', "
                        "'summary_artifacts', 'weekly_reflections', "
                        "'hour_logs', 'user_goals'"
                        ")"
                    )
                )
                self.assertEqual(table_count, 7)
                index_names = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE schemaname = current_schema()"
                            )
                        )
                    ).scalars()
                )
                self.assertIn(
                    "ix_continuity_embeddings_embedding_hnsw",
                    index_names,
                )
                self.assertIn("ix_days_daily_note_trgm", index_names)
                vector_type = await connection.scalar(
                    text(
                        "SELECT format_type(a.atttypid, a.atttypmod) "
                        "FROM pg_attribute AS a "
                        "WHERE a.attrelid = 'continuity_embeddings'::regclass "
                        "AND a.attname = 'embedding' AND a.attnum > 0 "
                        "AND NOT a.attisdropped"
                    )
                )
                self.assertEqual(vector_type, "vector(1024)")

            async with async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )() as db:
                user = User(
                    username="migration-integration-user",
                    email="migration-integration@example.com",
                    hashed_password=bcrypt.hashpw(
                        b"test-password", bcrypt.gensalt()
                    ).decode(),
                    is_verified=True,
                    ai_processing_consent=True,
                )
                db.add(user)
                await db.commit()
                return user.id

        with disposable_database() as database:
            database.run_alembic("upgrade", "head")
            database.run_alembic("check")
            database.run_alembic("downgrade", "base")
            database.run_alembic("upgrade", "head")
            engine = database.async_engine()
            try:
                user_id = asyncio.run(seed_and_inspect(engine))
                self._assert_api_round_trip(engine, user_id)
            finally:
                asyncio.run(engine.dispose())

    def _assert_api_round_trip(self, engine, user_id: int) -> None:
        import cadence.app as app_module

        app_instance = app_module.app
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async def override_get_db():
            async with session_factory() as db:
                yield db

        previous_engine = app_module.async_engine
        app_module.async_engine = engine
        app_instance.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app_instance) as client:
                response = client.put(
                    "/api/days/2026-08-15",
                    headers={"Authorization": f"Bearer {_create_token(user_id)}"},
                    json={"daily_note": "migrated API write"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["daily_note"], "migrated API write")
        finally:
            app_instance.dependency_overrides.clear()
            app_module.async_engine = previous_engine

        async def read_day() -> str:
            async with session_factory() as db:
                day = await db.scalar(
                    select(Day).where(
                        Day.user_id == user_id,
                        Day.date == date(2026, 8, 15),
                    )
                )
                return day.daily_note

        self.assertEqual(asyncio.run(read_day()), "migrated API write")


if __name__ == "__main__":
    unittest.main()

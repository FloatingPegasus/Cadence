from __future__ import annotations

import asyncio
import bcrypt
from datetime import date
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

if __package__ == "cadence.tests.integration":
    from ..bootstrap import configure_test_environment
    from .support import disposable_database, integration_enabled
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap import configure_test_environment
    from integration.support import disposable_database, integration_enabled

configure_test_environment()

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cadence.app.config import settings
from cadence.app.domains.contexts import service as contexts_service
from cadence.app.domains.continuity import service as continuity_service
from cadence.app.domains.days import service as days_service
from cadence.app.domains.habits import service as habits_service
from cadence.app.domains.summaries import service as summaries_service
from cadence.app.domains.weekly_reflections import service as reflections_service
from cadence.app.persistence.models.continuity_embedding import ContinuityEmbedding
from cadence.app.persistence.models.day import Day
from cadence.app.persistence.models.habit import Habit
from cadence.app.persistence.models.habit_log import HabitLog
from cadence.app.persistence.models.summary_artifact import SummaryArtifact
from cadence.app.persistence.models.user import User
from cadence.app.persistence.models.weekly_reflection import WeeklyReflection
from cadence.app.services import embeddings


@unittest.skipUnless(
    integration_enabled(),
    "set CADENCE_RUN_INTEGRATION=1 to run PostgreSQL integration tests",
)
class ConcurrencyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.database_context = disposable_database()
        try:
            cls.database = cls.database_context.__enter__()
            cls.database.run_alembic("upgrade", "head")
            cls.engine = cls.database.async_engine()
            cls.session_factory = async_sessionmaker(
                cls.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except BaseException:
            cls.database_context.__exit__(*sys.exc_info())
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            asyncio.run(cls.engine.dispose())
        finally:
            try:
                cls.database_context.__exit__(None, None, None)
            finally:
                super().tearDownClass()

    def setUp(self) -> None:
        asyncio.run(self._reset_database())

    async def _reset_database(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE users RESTART IDENTITY CASCADE")
            )

    async def _create_user(self, *, with_habit: bool = False) -> int:
        token = uuid4().hex
        async with self.session_factory() as db:
            user = User(
                username=f"integration-{token}",
                email=f"integration-{token}@example.com",
                hashed_password=bcrypt.hashpw(
                    b"test-password", bcrypt.gensalt()
                ).decode(),
                is_verified=True,
                ai_processing_consent=True,
            )
            db.add(user)
            await db.flush()
            if with_habit:
                db.add(Habit(user_id=user.id, name=f"Race {token}"))
            await db.commit()
            return user.id

    async def _run_duplicate_generations(
        self,
        generator,
        ai_module,
        count_query,
    ) -> int:
        user_id = await self._create_user()
        calls = 0
        second_call = asyncio.Event()
        release = asyncio.Event()

        async def provider(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                second_call.set()
            await release.wait()
            return {
                "provider": "nvidia",
                "model": "integration-model",
                "content": "generated content",
            }

        with patch.object(
            ai_module,
            "chat_with_fallback",
            new=AsyncMock(side_effect=provider),
        ):

            async def one_generation() -> None:
                async with self.session_factory() as db:
                    await generator(db, user_id)

            first = asyncio.create_task(one_generation())
            second = asyncio.create_task(one_generation())
            await asyncio.wait_for(second_call.wait(), timeout=5)
            release.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
            self.assertTrue(
                all(not isinstance(result, Exception) for result in results)
            )

        async with self.session_factory() as db:
            return await db.scalar(count_query(user_id))

    def test_failed_invalidation_cannot_surface_cleared_source(self) -> None:
        async def run() -> list[dict]:
            user_id = await self._create_user()
            async with self.session_factory() as db:
                day = Day(
                    user_id=user_id,
                    date=date(2026, 8, 12),
                    daily_note="source that will be cleared",
                )
                db.add(day)
                await db.flush()
                db.add(
                    ContinuityEmbedding(
                        user_id=user_id,
                        source_type="notes",
                        source_id=day.id,
                        day_id=day.id,
                        source_date=day.date,
                        content=day.daily_note,
                        content_hash=embeddings._content_hash(day.daily_note),
                        embedding_model=settings.embedding_model,
                        embedding=[0.1] * 1024,
                        is_current=True,
                    )
                )
                await db.commit()
                day.daily_note = ""
                await db.commit()
                with patch.object(
                    embeddings,
                    "_clear_source_embedding",
                    new=AsyncMock(side_effect=RuntimeError("invalidation failed")),
                ):
                    self.assertFalse(
                        await embeddings._sync_source_embedding(
                            db,
                            user_id=user_id,
                            source_type="notes",
                            source_id=day.id,
                            content="",
                            day_id=day.id,
                            source_date=day.date,
                        )
                    )
                with patch.object(
                    continuity_service.embedding_service,
                    "embed_text",
                    new=AsyncMock(return_value=[0.1] * 1024),
                ):
                    return await continuity_service._semantic_search(
                        db,
                        user_id,
                        "source",
                        date(2026, 8, 1),
                        date(2026, 8, 31),
                        "notes",
                        20,
                        None,
                    )

        self.assertEqual(asyncio.run(run()), [])

    def test_concurrent_summary_generation_preserves_manual_edit(self) -> None:
        async def run() -> str:
            user_id = await self._create_user()
            started = asyncio.Event()
            release = asyncio.Event()

            async def provider(*_args, **_kwargs):
                started.set()
                await release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "generated content",
                }

            with patch.object(
                summaries_service.ai_service,
                "chat_with_fallback",
                new=AsyncMock(side_effect=provider),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        summaries_service.generate_daily_summary(
                            generated_db,
                            user_id,
                            date(2026, 8, 12),
                        )
                    )
                    await asyncio.wait_for(started.wait(), timeout=5)
                    async with self.session_factory() as manual_db:
                        await summaries_service.save_manual_summary(
                            manual_db,
                            user_id,
                            date(2026, 8, 12),
                            "manual content wins",
                        )
                    release.set()
                    await generation
            async with self.session_factory() as db:
                artifact = await db.scalar(
                    select(SummaryArtifact)
                    .join(Day)
                    .where(
                        Day.user_id == user_id,
                        Day.date == date(2026, 8, 12),
                    )
                )
                return artifact.content

        self.assertEqual(asyncio.run(run()), "manual content wins")

    def test_summary_generation_rejects_source_change_during_provider(self) -> None:
        async def run() -> None:
            user_id = await self._create_user()
            started = asyncio.Event()
            release = asyncio.Event()

            async def provider(*_args, **_kwargs):
                started.set()
                await release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "stale generated content",
                }

            with patch.object(
                summaries_service.ai_service,
                "chat_with_fallback",
                new=AsyncMock(side_effect=provider),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        summaries_service.generate_daily_summary(
                            generated_db,
                            user_id,
                            date(2026, 8, 12),
                        )
                    )
                    await asyncio.wait_for(started.wait(), timeout=5)
                    async with self.session_factory() as source_db:
                        await source_db.execute(
                            update(Day)
                            .where(
                                Day.user_id == user_id,
                                Day.date == date(2026, 8, 12),
                            )
                            .values(daily_note="changed while generating")
                        )
                        await source_db.commit()
                    release.set()
                    with self.assertRaisesRegex(
                        ValueError,
                        "Source changed while generating",
                    ):
                        await generation

            async with self.session_factory() as db:
                self.assertIsNone(
                    await db.scalar(
                        select(SummaryArtifact)
                        .join(Day)
                        .where(
                            Day.user_id == user_id,
                            Day.date == date(2026, 8, 12),
                        )
                    )
                )

        asyncio.run(run())

    def test_summary_write_lock_serializes_source_change_after_recheck(self) -> None:
        async def run() -> None:
            user_id = await self._create_user()
            target_date = date(2026, 8, 12)
            provider_started = asyncio.Event()
            provider_release = asyncio.Event()
            final_write_paused = asyncio.Event()
            final_write_release = asyncio.Event()
            source_lock_attempted = asyncio.Event()
            source_finished = asyncio.Event()

            async def provider(*_args, **_kwargs):
                provider_started.set()
                await provider_release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "serialized generated content",
                }

            class PausingSession(AsyncSession):
                async def execute(self, statement, *args, **kwargs):
                    table = getattr(statement, "table", None)
                    if (
                        getattr(table, "name", None)
                        == SummaryArtifact.__tablename__
                        and not final_write_paused.is_set()
                    ):
                        final_write_paused.set()
                        await final_write_release.wait()
                    return await super().execute(statement, *args, **kwargs)

            original_lock = days_service.acquire_continuity_lock

            async def source_lock(db, source_user_id):
                if db.info.get("source_race"):
                    source_lock_attempted.set()
                return await original_lock(db, source_user_id)

            with (
                patch.object(
                    summaries_service.ai_service,
                    "chat_with_fallback",
                    new=AsyncMock(side_effect=provider),
                ),
                patch.object(summaries_service, "AsyncSession", PausingSession),
                patch.object(days_service, "acquire_continuity_lock", source_lock),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        summaries_service.generate_daily_summary(
                            generated_db,
                            user_id,
                            target_date,
                        )
                    )
                    await asyncio.wait_for(provider_started.wait(), timeout=5)
                    provider_release.set()
                    await asyncio.wait_for(
                        final_write_paused.wait(),
                        timeout=5,
                    )

                    async def mutate_source() -> None:
                        async with self.session_factory() as source_db:
                            source_db.info["source_race"] = True
                            await days_service.update_day(
                                source_db,
                                user_id,
                                target_date,
                                "changed after final recheck",
                            )
                            source_finished.set()

                    source_task = asyncio.create_task(mutate_source())
                    await asyncio.wait_for(
                        source_lock_attempted.wait(),
                        timeout=5,
                    )
                    self.assertFalse(source_finished.is_set())
                    final_write_release.set()
                    await generation
                    await source_task

            async with self.session_factory() as db:
                artifact = await db.scalar(
                    select(SummaryArtifact)
                    .join(Day)
                    .where(
                        Day.user_id == user_id,
                        Day.date == target_date,
                    )
                )
                day, snapshot = await summaries_service.build_source_snapshot(
                    db,
                    user_id,
                    target_date,
                )
                current_fingerprint, _ = summaries_service.fingerprint(snapshot)
                self.assertEqual(artifact.content, "serialized generated content")
                self.assertEqual(day.daily_note, "changed after final recheck")
                self.assertNotEqual(
                    artifact.source_fingerprint,
                    current_fingerprint,
                )

        asyncio.run(run())

    def test_concurrent_first_summary_generations_create_one_row(self) -> None:
        async def generate(db: AsyncSession, user_id: int) -> dict:
            return await summaries_service.generate_daily_summary(
                db,
                user_id,
                date(2026, 8, 12),
            )

        def count_query(user_id: int):
            return select(func.count(SummaryArtifact.id)).join(Day).where(
                Day.user_id == user_id,
                Day.date == date(2026, 8, 12),
            )

        count = asyncio.run(
            self._run_duplicate_generations(
                generate,
                summaries_service.ai_service,
                count_query,
            )
        )
        self.assertEqual(count, 1)

    def test_concurrent_reflection_generation_preserves_manual_edit(self) -> None:
        async def run() -> str:
            user_id = await self._create_user()
            started = asyncio.Event()
            release = asyncio.Event()

            async def provider(*_args, **_kwargs):
                started.set()
                await release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "generated reflection",
                }

            with patch.object(
                reflections_service.ai_service,
                "chat_with_fallback",
                new=AsyncMock(side_effect=provider),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        reflections_service.generate_weekly_reflection(
                            generated_db,
                            user_id,
                            date(2026, 8, 12),
                        )
                    )
                    await asyncio.wait_for(started.wait(), timeout=5)
                    async with self.session_factory() as manual_db:
                        await reflections_service.save_manual_reflection(
                            manual_db,
                            user_id,
                            date(2026, 8, 12),
                            "manual reflection wins",
                        )
                    release.set()
                    await generation
            async with self.session_factory() as db:
                reflection = await db.scalar(
                    select(WeeklyReflection).where(
                        WeeklyReflection.user_id == user_id,
                    )
                )
                return reflection.content

        self.assertEqual(asyncio.run(run()), "manual reflection wins")

    def test_weekly_snapshot_lock_prevents_mixed_subqueries(self) -> None:
        async def run() -> None:
            user_id = await self._create_user(with_habit=True)
            target_date = date(2026, 8, 12)
            async with self.session_factory() as db:
                habit_id = await db.scalar(
                    select(Habit.id).where(Habit.user_id == user_id)
                )
                db.add(
                    Day(
                        user_id=user_id,
                        date=target_date,
                        daily_note="weekly snapshot source",
                    )
                )
                await db.commit()

            first_week_query = asyncio.Event()
            release_first_week_query = asyncio.Event()
            source_lock_attempted = asyncio.Event()
            source_finished = asyncio.Event()
            provider_started = asyncio.Event()
            provider_release = asyncio.Event()
            captured_snapshots: list[dict] = []

            async def provider(*_args, **kwargs):
                captured_snapshots.append(
                    json.loads(kwargs["messages"][1]["content"])
                )
                provider_started.set()
                await provider_release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "generated reflection",
                }

            class PausingSession(AsyncSession):
                async def execute(self, statement, *args, **kwargs):
                    result = await super().execute(statement, *args, **kwargs)
                    if (
                        self.info.get("pause_weekly_query")
                        and not first_week_query.is_set()
                    ):
                        first_week_query.set()
                        await release_first_week_query.wait()
                    return result

            original_reflection_lock = (
                reflections_service.acquire_continuity_lock
            )

            async def reflection_lock(db, source_user_id):
                result = await original_reflection_lock(db, source_user_id)
                db.info["pause_weekly_query"] = True
                return result

            original_source_lock = habits_service.acquire_continuity_lock

            async def source_lock(db, source_user_id):
                if db.info.get("weekly_source"):
                    source_lock_attempted.set()
                return await original_source_lock(db, source_user_id)

            async def mutate_source() -> None:
                async with self.session_factory() as source_db:
                    source_db.info["weekly_source"] = True
                    await habits_service.toggle_habit(
                        source_db,
                        user_id,
                        habit_id,
                        target_date,
                        "1",
                    )
                    source_finished.set()

            with (
                patch.object(
                    reflections_service.ai_service,
                    "chat_with_fallback",
                    new=AsyncMock(side_effect=provider),
                ),
                patch.object(
                    reflections_service,
                    "AsyncSession",
                    PausingSession,
                ),
                patch.object(
                    reflections_service,
                    "acquire_continuity_lock",
                    reflection_lock,
                ),
                patch.object(
                    habits_service,
                    "acquire_continuity_lock",
                    source_lock,
                ),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        reflections_service.generate_weekly_reflection(
                            generated_db,
                            user_id,
                            target_date,
                        )
                    )
                    await asyncio.wait_for(
                        first_week_query.wait(),
                        timeout=5,
                    )
                    source_task = asyncio.create_task(mutate_source())
                    await asyncio.wait_for(
                        source_lock_attempted.wait(),
                        timeout=5,
                    )
                    self.assertFalse(source_finished.is_set())

                    release_first_week_query.set()
                    await asyncio.wait_for(
                        source_finished.wait(),
                        timeout=5,
                    )
                    await asyncio.wait_for(
                        provider_started.wait(),
                        timeout=5,
                    )
                    target_snapshot_day = next(
                        day
                        for day in captured_snapshots[0]["days"]
                        if day["date"] == target_date.isoformat()
                    )
                    self.assertEqual(
                        target_snapshot_day["habit_completions"],
                        0,
                    )
                    provider_release.set()
                    with self.assertRaisesRegex(
                        ValueError,
                        "Source changed while generating",
                    ):
                        await generation
                    await source_task

            async with self.session_factory() as db:
                self.assertIsNone(
                    await db.scalar(
                        select(WeeklyReflection).where(
                            WeeklyReflection.user_id == user_id,
                        )
                    )
                )

        asyncio.run(run())

    def test_reflection_generation_rejects_source_change_during_provider(
        self,
    ) -> None:
        async def run() -> None:
            user_id = await self._create_user()
            started = asyncio.Event()
            release = asyncio.Event()

            async def provider(*_args, **_kwargs):
                started.set()
                await release.wait()
                return {
                    "provider": "nvidia",
                    "model": "integration-model",
                    "content": "stale generated reflection",
                }

            with patch.object(
                reflections_service.ai_service,
                "chat_with_fallback",
                new=AsyncMock(side_effect=provider),
            ):
                async with self.session_factory() as generated_db:
                    generation = asyncio.create_task(
                        reflections_service.generate_weekly_reflection(
                            generated_db,
                            user_id,
                            date(2026, 8, 12),
                        )
                    )
                    await asyncio.wait_for(started.wait(), timeout=5)
                    async with self.session_factory() as source_db:
                        source_db.add(
                            Day(
                                user_id=user_id,
                                date=date(2026, 8, 12),
                                daily_note="changed while generating",
                            )
                        )
                        await source_db.commit()
                    release.set()
                    with self.assertRaisesRegex(
                        ValueError,
                        "Source changed while generating",
                    ):
                        await generation

            async with self.session_factory() as db:
                self.assertIsNone(
                    await db.scalar(
                        select(WeeklyReflection).where(
                            WeeklyReflection.user_id == user_id,
                        )
                    )
                )

        asyncio.run(run())

    def test_concurrent_first_reflection_generations_create_one_row(self) -> None:
        async def generate(db: AsyncSession, user_id: int) -> dict:
            return await reflections_service.generate_weekly_reflection(
                db,
                user_id,
                date(2026, 8, 12),
            )

        def count_query(user_id: int):
            return select(func.count(WeeklyReflection.id)).where(
                WeeklyReflection.user_id == user_id,
                WeeklyReflection.week_start == date(2026, 8, 10),
            )

        count = asyncio.run(
            self._run_duplicate_generations(
                generate,
                reflections_service.ai_service,
                count_query,
            )
        )
        self.assertEqual(count, 1)

    def test_concurrent_first_habit_toggle_is_idempotent(self) -> None:
        async def run() -> tuple[int, int]:
            user_id = await self._create_user(with_habit=True)
            async with self.session_factory() as db:
                habit_id = await db.scalar(
                    select(Habit.id).where(Habit.user_id == user_id)
                )

            async def toggle() -> None:
                async with self.session_factory() as db:
                    await habits_service.toggle_habit(
                        db,
                        user_id,
                        habit_id,
                        date(2026, 8, 12),
                        "1",
                    )

            await asyncio.gather(toggle(), toggle())
            async with self.session_factory() as db:
                day_count = await db.scalar(
                    select(func.count(Day.id)).where(
                        Day.user_id == user_id,
                        Day.date == date(2026, 8, 12),
                    )
                )
                log_count = await db.scalar(
                    select(func.count(HabitLog.id))
                    .join(Day)
                    .where(
                        Day.user_id == user_id,
                        Day.date == date(2026, 8, 12),
                    )
                )
                return day_count, log_count

        self.assertEqual(asyncio.run(run()), (1, 1))

    def test_concurrent_day_creation_is_idempotent(self) -> None:
        async def run() -> tuple[list[int], int]:
            user_id = await self._create_user()
            target_date = date(2026, 8, 12)

            async def create() -> int:
                async with self.session_factory() as db:
                    day = await days_service.get_or_create_day(
                        db,
                        user_id,
                        target_date,
                    )
                    await db.commit()
                    return day.id

            day_ids = await asyncio.gather(create(), create())
            async with self.session_factory() as db:
                count = await db.scalar(
                    select(func.count(Day.id)).where(
                        Day.user_id == user_id,
                        Day.date == target_date,
                    )
                )
            return day_ids, count

        day_ids, count = asyncio.run(run())
        self.assertEqual(day_ids[0], day_ids[1])
        self.assertEqual(count, 1)

    def test_invalid_context_assignment_does_not_create_day(self) -> None:
        async def run() -> None:
            user_id = await self._create_user()
            target_date = date(2026, 8, 12)
            async with self.session_factory() as db:
                with self.assertRaises(contexts_service.ContextNotFoundError):
                    await contexts_service.set_for_day(
                        db,
                        user_id,
                        target_date,
                        [999999],
                    )
                await db.rollback()

            async with self.session_factory() as db:
                self.assertIsNone(
                    await db.scalar(
                        select(Day.id).where(
                            Day.user_id == user_id,
                            Day.date == target_date,
                        )
                    )
                )

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

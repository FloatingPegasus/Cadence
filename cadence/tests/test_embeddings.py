import asyncio
import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

import httpx
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from cadence.app.config import settings
from cadence.app.domains.continuity import service as continuity_service
from cadence.app import extensions
from cadence.app.persistence.models.day import Day
from cadence.app.services import embeddings
from cadence.app.web.routes.continuity import search as continuity_search_route
from cadence import maintenance


class EmbeddingProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_ai_enabled = settings.ai_enabled
        self.original_ai_api_key = settings.ai_api_key
        self.original_embedding_enabled = settings.embedding_enabled
        self.original_input_cap = settings.embedding_input_max_chars
        settings.ai_enabled = True
        settings.ai_api_key = "test-key"
        settings.embedding_enabled = True

    def tearDown(self) -> None:
        settings.ai_enabled = self.original_ai_enabled
        settings.ai_api_key = self.original_ai_api_key
        settings.embedding_enabled = self.original_embedding_enabled
        settings.embedding_input_max_chars = self.original_input_cap

    def test_embedding_session_resolves_caller_engine_not_global_engine(self) -> None:
        caller_engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )
        caller_session = AsyncSession(bind=caller_engine)
        resolved_engine = None
        owns_engine = False
        try:
            with patch.object(
                embeddings,
                "create_async_engine",
                side_effect=AssertionError(
                    "ordinary bound sessions must reuse their engine"
                ),
            ):
                resolved_engine, owns_engine = embeddings._caller_async_engine(
                    caller_session
                )
            self.assertEqual(resolved_engine.url, caller_engine.url)
            self.assertIs(resolved_engine, caller_engine)
            self.assertFalse(owns_engine)
            self.assertIsNot(resolved_engine, extensions.async_engine)
        finally:
            async def close() -> None:
                await caller_session.close()
                if owns_engine and resolved_engine is not None:
                    await resolved_engine.dispose()
                await caller_engine.dispose()

            asyncio.run(close())

    def test_sync_uses_alternate_bind_for_embedding_session(self) -> None:
        caller_engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )
        caller_session = AsyncSession(bind=caller_engine)
        observed = {}

        async def fake_sync(embedding_db, **_kwargs):
            observed["bind"] = embedding_db.bind
            return True

        async def run() -> bool:
            with (
                patch.object(
                    embeddings,
                    "_sync_source_embedding",
                    new=AsyncMock(side_effect=fake_sync),
                ),
                patch.object(
                    embeddings,
                    "create_async_engine",
                    side_effect=AssertionError(
                        "alternate bound sessions must reuse their engine"
                    ),
                ),
            ):
                return await embeddings.sync_source_embedding(
                    caller_session,
                    user_id=1,
                    source_type="notes",
                    source_id=2,
                    content="alternate bind",
                )

        try:
            self.assertTrue(asyncio.run(run()))
            self.assertIsNot(observed["bind"], extensions.async_engine)
            self.assertIs(observed["bind"], caller_engine)
        finally:
            async def close() -> None:
                await caller_session.close()
                await caller_engine.dispose()

            asyncio.run(close())

    def test_backfill_uses_explicit_psycopg_migration_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CADENCE_MIGRATION_DATABASE_URL": (
                    "postgresql://user:password@direct-host:5432/cadence"
                )
            },
        ):
            url = maintenance._migration_async_url()
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.host, "direct-host")

    def test_backfill_reuses_explicit_session_without_creating_engines(self) -> None:
        class Result:
            def __init__(self, rows):
                self.rows = rows

            def all(self):
                return self.rows

        class FakeDatabase:
            def __init__(self):
                self.execute_count = 0

            async def execute(self, _statement):
                self.execute_count += 1
                if self.execute_count == 1:
                    return Result(
                        [
                            (
                                SimpleNamespace(
                                    id=1,
                                    user_id=7,
                                    daily_note="first source",
                                    date=date(2026, 8, 1),
                                ),
                                None,
                            ),
                            (
                                SimpleNamespace(
                                    id=2,
                                    user_id=7,
                                    daily_note="second source",
                                    date=date(2026, 8, 2),
                                ),
                                None,
                            ),
                        ]
                    )
                return Result([])

            async def rollback(self):
                return None

        async def run():
            with (
                patch.object(
                    embeddings,
                    "create_async_engine",
                    side_effect=AssertionError(
                        "maintenance backfill must not create per-source engines"
                    ),
                ),
                patch.object(
                    embeddings,
                    "_caller_async_engine",
                    side_effect=AssertionError(
                        "maintenance backfill already has an explicit engine"
                    ),
                ),
                patch.object(
                    embeddings,
                    "_sync_source_embedding",
                    new=AsyncMock(return_value=True),
                ) as refresh,
            ):
                result = await embeddings.backfill_embeddings(
                    FakeDatabase(),
                    batch_size=2,
                )
                return result, refresh

        result, refresh = asyncio.run(run())
        self.assertEqual(result, {"attempted": 2, "refreshed": 2, "failed": 0})
        self.assertEqual(refresh.await_count, 2)

    def test_nvidia_request_uses_query_or_passage_and_redacts_input(self) -> None:
        requests: list[dict] = []
        settings.embedding_input_max_chars = 64

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.25] * 1024},
                    ]
                },
            )

        async def run() -> tuple[list[float], list[float]]:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                passage = await embeddings.embed_text(
                    "Email me at alpha@example.com",
                    input_type="passage",
                    redaction_enabled=True,
                    client=client,
                )
                query = await embeddings.embed_text(
                    "continuity query",
                    input_type="query",
                    redaction_enabled=False,
                    client=client,
                )
                return passage, query

        passage, query = asyncio.run(run())
        self.assertEqual(len(passage), 1024)
        self.assertEqual(len(query), 1024)
        self.assertEqual(requests[0]["input_type"], "passage")
        self.assertEqual(requests[1]["input_type"], "query")
        self.assertEqual(requests[0]["model"], "nvidia/nv-embedqa-e5-v5")
        self.assertEqual(requests[0]["encoding_format"], "float")
        self.assertEqual(requests[0]["truncate"], "END")
        self.assertNotIn("alpha@example.com", requests[0]["input"])
        self.assertIn("[redacted email]", requests[0]["input"])
        self.assertLessEqual(len(requests[0]["input"]), 64)

    def test_provider_rejects_non_finite_vectors(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": [{"embedding": [float("nan")] * 1024}]},
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with self.assertRaises(embeddings.EmbeddingProviderError):
                    await embeddings.embed_text(
                        "query",
                        input_type="query",
                        redaction_enabled=True,
                        client=client,
                    )

        asyncio.run(run())

    def test_provider_rejects_zero_and_near_zero_vectors(self) -> None:
        for value in (0.0, 1e-9):
            def handler(_request: httpx.Request, value=value) -> httpx.Response:
                return httpx.Response(
                    200,
                    json={"data": [{"embedding": [value] * 1024}]},
                )

            async def run() -> None:
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    with self.assertRaises(embeddings.EmbeddingProviderError):
                        await embeddings.embed_text(
                            "query",
                            input_type="query",
                            redaction_enabled=True,
                            client=client,
                        )

            asyncio.run(run())

    def test_backfill_compares_normalized_hash_model_and_current_state(self) -> None:
        class Existing:
            id = 7
            is_current = True
            content = "same text"
            content_hash = embeddings._content_hash("same text")
            embedding_model = settings.embedding_model

        self.assertFalse(
            embeddings._needs_backfill("  same text  ", Existing())
        )
        stale_hash = Existing()
        stale_hash.content_hash = "0" * 64
        self.assertTrue(embeddings._needs_backfill("same text", stale_hash))
        stale_model = Existing()
        stale_model.embedding_model = "old-model"
        self.assertTrue(embeddings._needs_backfill("same text", stale_model))
        non_current = Existing()
        non_current.is_current = False
        self.assertTrue(embeddings._needs_backfill("same text", non_current))
        self.assertTrue(embeddings._needs_backfill("", Existing()))
        self.assertFalse(embeddings._needs_backfill("", None))

    def test_sql_backfill_predicate_targets_missing_or_stale_rows(self) -> None:
        predicate = embeddings._sql_needs_backfill(Day.daily_note)
        compiled = str(predicate.compile(dialect=postgresql.dialect())).lower()

        self.assertEqual(len(predicate.clauses), 5)
        self.assertIn("continuity_embeddings.id is null", compiled)
        self.assertIn("continuity_embeddings.is_current is false", compiled)
        self.assertIn("continuity_embeddings.embedding_model !=", compiled)
        self.assertIn("trim(coalesce(days.daily_note", compiled)

    def test_sql_hash_predicate_is_current_same_model_content_check(self) -> None:
        predicate = embeddings._sql_hash_check(Day.daily_note)
        compiled = str(predicate.compile(dialect=postgresql.dialect())).lower()

        self.assertEqual(len(predicate.clauses), 4)
        self.assertIn("continuity_embeddings.id is not null", compiled)
        self.assertIn("continuity_embeddings.is_current is true", compiled)
        self.assertIn("continuity_embeddings.embedding_model =", compiled)
        self.assertIn("continuity_embeddings.content", compiled)
        self.assertIn("trim(coalesce(days.daily_note", compiled)

    def test_clear_source_embedding_removes_by_source_key_not_hash(self) -> None:
        class Result:
            rowcount = 1

        class FakeDatabase:
            def __init__(self):
                self.statement = None

            async def execute(self, statement):
                self.statement = statement
                return Result()

            async def commit(self):
                return None

        db = FakeDatabase()

        async def run():
            return await embeddings._clear_source_embedding(
                db,
                user_id=1,
                source_type="notes",
                source_id=2,
                content="",
            )

        self.assertTrue(asyncio.run(run()))
        compiled = str(
            db.statement.compile(dialect=postgresql.dialect())
        ).lower()
        self.assertIn("delete from continuity_embeddings", compiled)
        self.assertNotIn("content_hash", compiled)

    def test_placeholder_is_atomic_upsert_and_preserves_same_current_vector(
        self,
    ) -> None:
        class Existing:
            id = 7
            is_current = True
            content_hash = embeddings._content_hash("same text")
            embedding_model = settings.embedding_model

        class Result:
            def first(self):
                return None

        class FakeDatabase:
            def __init__(self):
                self.statements = []
                self.scalar_calls = 0

            async def scalar(self, _statement):
                self.scalar_calls += 1
                if self.scalar_calls <= 2:
                    return True
                return Existing()

            async def execute(self, statement):
                self.statements.append(statement)
                return Result()

            async def commit(self):
                return None

            async def rollback(self):
                return None

        db = FakeDatabase()

        async def run():
            return await embeddings._prepare_placeholder(
                db,
                user_id=1,
                source_type="notes",
                source_id=2,
                content="same text",
                content_hash=Existing.content_hash,
                day_id=2,
                source_date=date(2026, 8, 2),
                return_id=True,
            )

        self.assertEqual(asyncio.run(run()), (True, False, 7))
        compiled = str(
            db.statements[0].compile(dialect=postgresql.dialect())
        ).lower()
        self.assertIn("insert into continuity_embeddings", compiled)
        self.assertIn("on conflict", compiled)
        self.assertIn("is distinct from", compiled)
        self.assertIn("returning", compiled)

    def test_iterative_hnsw_scan_setting_is_best_effort(self) -> None:
        class FakeDatabase:
            def __init__(self):
                self.statement = None

            async def execute(self, statement):
                self.statement = statement

            async def rollback(self):
                return None

        db = FakeDatabase()
        asyncio.run(continuity_service._enable_iterative_hnsw_scan(db))
        self.assertIn(
            "hnsw.iterative_scan",
            str(db.statement).lower(),
        )

    def test_iterative_scan_failure_configures_exact_fallback(self) -> None:
        class FakeDatabase:
            def __init__(self):
                self.statements = []
                self.calls = 0

            async def execute(self, statement):
                self.calls += 1
                self.statements.append(statement)
                if self.calls == 1:
                    raise RuntimeError("old pgvector")

            async def rollback(self):
                return None

        db = FakeDatabase()
        self.assertFalse(
            asyncio.run(continuity_service._enable_iterative_hnsw_scan(db))
        )
        rendered = " ".join(str(statement) for statement in db.statements)
        self.assertIn("enable_indexscan", rendered)
        self.assertIn("enable_bitmapscan", rendered)

    def test_whitespace_query_is_rejected_before_provider_call(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.25] * 1024}]},
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with self.assertRaises(embeddings.EmbeddingProviderError):
                    await embeddings.embed_text(
                        " \t\n ",
                        input_type="query",
                        redaction_enabled=True,
                        client=client,
                    )

        asyncio.run(run())
        self.assertEqual(requests, [])

    def test_merge_deduplicates_semantic_rows_and_honors_limit(self) -> None:
        semantic = [
            {
                "source": "notes",
                "source_id": 2,
                "date": "2026-08-02",
                "title": "Daily note",
                "excerpt": "nearest",
                "_semantic_rank": 0.1,
            },
            {
                "source": "notes",
                "source_id": 1,
                "date": "2026-08-01",
                "title": "Daily note",
                "excerpt": "next",
                "_semantic_rank": 0.2,
            },
        ]
        lexical = [
            {
                "source": "notes",
                "source_id": 2,
                "date": "2026-08-02",
                "title": "Daily note",
                "excerpt": "exact duplicate",
            },
            {
                "source": "threads",
                "source_id": 9,
                "date": "2026-08-01",
                "title": "Follow-up",
                "excerpt": "lexical",
                "status": "open",
            },
        ]

        merged = continuity_service._merge_search_results(
            semantic,
            lexical,
            2,
        )

        self.assertEqual(
            [(item["source"], item["source_id"]) for item in merged],
            [("notes", 2), ("notes", 1)],
        )
        self.assertNotIn("_semantic_rank", merged[0])

    def test_semantic_query_releases_read_transaction_before_provider(self) -> None:
        class Result:
            def one_or_none(self):
                return (True, True)

            def all(self):
                return []

        class FakeDatabase:
            def __init__(self):
                self.in_transaction = True
                self.execute_count = 0

            async def execute(self, _statement):
                self.execute_count += 1
                return Result()

            async def scalar(self, _statement):
                return None

            async def rollback(self):
                self.in_transaction = False

        db = FakeDatabase()
        observed = []

        async def fake_embed(*_args, **_kwargs):
            observed.append(db.in_transaction)
            return [0.1] * 1024

        async def run():
            with patch.object(
                continuity_service.embedding_service,
                "embed_text",
                side_effect=fake_embed,
            ):
                return await continuity_service._semantic_search(
                    db,
                    1,
                    "query",
                    date(2026, 8, 1),
                    date(2026, 8, 31),
                    "all",
                    20,
                    None,
                )

        self.assertEqual(asyncio.run(run()), [])
        self.assertEqual(observed, [False])

    def test_semantic_provider_failure_keeps_lexical_payload(self) -> None:
        expected = {
            "query": "query",
            "source": "all",
            "context_id": None,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "results": [
                {
                    "source": "notes",
                    "source_id": 3,
                    "date": "2026-08-03",
                    "title": "Daily note",
                    "excerpt": "lexical",
                }
            ],
        }

        async def run():
            with (
                patch.object(
                    continuity_service,
                    "_semantic_search",
                    new=AsyncMock(return_value=[]),
                ),
                patch.object(
                    continuity_service,
                    "_lexical_search",
                    new=AsyncMock(return_value=expected),
                ),
            ):
                return await continuity_service.search(
                    object(),
                    1,
                    " query ",
                    date(2026, 8, 1),
                    date(2026, 8, 31),
                )

        self.assertEqual(asyncio.run(run()), expected)

    def test_semantic_database_failure_rolls_back_and_keeps_lexical(self) -> None:
        class FailedDatabase:
            def __init__(self):
                self.rolled_back = False

            async def execute(self, _statement):
                raise SQLAlchemyError("optional embedding query failed")

            async def rollback(self):
                self.rolled_back = True

        db = FailedDatabase()
        expected = {
            "query": "query",
            "source": "all",
            "context_id": None,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "results": [],
        }

        async def run():
            with patch.object(
                continuity_service,
                "_lexical_search",
                new=AsyncMock(return_value=expected),
            ):
                return await continuity_service.search(
                    db,
                    1,
                    "query",
                    date(2026, 8, 1),
                    date(2026, 8, 31),
                )

        self.assertEqual(asyncio.run(run()), expected)
        self.assertTrue(db.rolled_back)

    def test_route_rejects_whitespace_only_query(self) -> None:
        async def run():
            with self.assertRaises(HTTPException) as raised:
                await continuity_search_route(
                    q=" \t ",
                    start_date=date(2026, 8, 1),
                    end_date=date(2026, 8, 31),
                    db=object(),
                    user=object(),
                )
            return raised.exception.status_code

        self.assertEqual(asyncio.run(run()), 422)

    def test_route_rejects_one_character_after_normalization(self) -> None:
        async def run():
            with self.assertRaises(HTTPException) as raised:
                await continuity_search_route(
                    q=" a",
                    start_date=date(2026, 8, 1),
                    end_date=date(2026, 8, 31),
                    db=object(),
                    user=object(),
                )
            return raised.exception.status_code

        self.assertEqual(asyncio.run(run()), 422)

    def test_service_rejects_one_character_after_normalization(self) -> None:
        async def run():
            return await continuity_service.search(
                object(),
                1,
                " a",
                date(2026, 8, 1),
                date(2026, 8, 31),
            )

        result = asyncio.run(run())
        self.assertEqual(result["query"], "a")
        self.assertEqual(result["results"], [])

    def test_activation_is_update_only_and_contains_content_cas(self) -> None:
        class Result:
            rowcount = 0

        class FakeDatabase:
            def __init__(self):
                self.statement = None

            async def execute(self, statement):
                self.statement = statement
                return Result()

            async def commit(self):
                return None

        db = FakeDatabase()

        async def run():
            return await embeddings._activate_embedding(
                db,
                user_id=1,
                source_type="notes",
                source_id=2,
                content="latest",
                content_hash="a" * 64,
                placeholder_id=2,
                day_id=2,
                source_date=date(2026, 8, 2),
                vector=[0.1] * 1024,
            )

        self.assertFalse(asyncio.run(run()))
        compiled = str(
            db.statement.compile(dialect=postgresql.dialect())
        ).lower()
        self.assertIn("update continuity_embeddings", compiled)
        self.assertIn("content_hash", compiled)
        self.assertIn("embedding_model", compiled)
        self.assertNotIn("insert into continuity_embeddings", compiled)


if __name__ == "__main__":
    unittest.main()

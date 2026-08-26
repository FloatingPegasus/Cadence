import asyncio
from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

import httpx

import cadence.app as app_module
from cadence.app.config import Settings, settings
from cadence.app.persistence.models.ai_model import AIModel
from cadence.app.services import ai as ai_service
from cadence.app.services import embeddings
from cadence.app.web.routes import auth


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        if self.value is None:
            return []
        return self.value if isinstance(self.value, list) else [self.value]


class _Session:
    def __init__(self, result=None, commit_error=None):
        self.result = result
        self.commit_error = commit_error
        self.active = False
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        self.active = True
        return self

    async def __aexit__(self, *_args):
        self.active = False

    async def execute(self, _statement):
        return _Result(self.result)

    async def get(self, _model, _user_id):
        return self.result

    async def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error
        self.active = False

    async def rollback(self):
        self.rollbacks += 1
        self.active = False


class _SessionFactory:
    def __init__(self, result, commit_error=None):
        self.result = result
        self.commit_error = commit_error
        self.sessions = []

    def __call__(self):
        session = _Session(self.result, self.commit_error)
        self.sessions.append(session)
        return session


class _ProviderClient:
    def __init__(self, response, observed=None):
        self.response = response
        self.observed = observed
        self.closed = False

    async def post(self, *_args, **_kwargs):
        if self.observed is not None:
            self.observed.append(True)
        return self.response

    async def aclose(self):
        self.closed = True


class AIExternalIOHardeningTests(unittest.TestCase):
    def setUp(self):
        self.original_ai_enabled = settings.ai_enabled
        self.original_ai_api_key = settings.ai_api_key
        settings.ai_enabled = True
        settings.ai_api_key = "test-key"

    def tearDown(self):
        settings.ai_enabled = self.original_ai_enabled
        settings.ai_api_key = self.original_ai_api_key

    def _model(self):
        return AIModel(
            id=1,
            provider="nvidia",
            model_id="example/model",
            strength_score=50,
            ranking_version=ai_service.RANKING_VERSION,
            enabled=True,
            health_status="untested",
            last_seen_at=datetime(2026, 8, 1),
        )

    def test_probe_uses_independent_sessions_and_closes_owned_client(self):
        model = self._model()
        factory = _SessionFactory(model, RuntimeError("commit failed"))
        caller = SimpleNamespace(commits=0, rollbacks=0)
        observed = []
        provider = _ProviderClient(
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "CADENCE_OK"}}]},
                request=httpx.Request(
                    "POST", "https://provider.test/v1/chat/completions"
                ),
            ),
            observed,
        )

        async def run():
            with (
                patch.object(
                    ai_service,
                    "_caller_async_engine",
                    return_value=(object(), False),
                ),
                patch.object(
                    ai_service,
                    "_catalog_session_factory",
                    return_value=factory,
                ),
                patch.object(
                    ai_service.httpx,
                    "AsyncClient",
                    return_value=provider,
                ),
            ):
                return await ai_service.probe_model(caller, "example/model")

        result = asyncio.run(run())
        self.assertEqual(result["health_status"], "healthy")
        self.assertEqual(caller.commits, 0)
        self.assertEqual(caller.rollbacks, 0)
        self.assertTrue(provider.closed)
        self.assertEqual(len(factory.sessions), 2)
        self.assertTrue(all(not session.active for session in factory.sessions))
        self.assertEqual(observed, [True])

    def test_probe_does_not_mark_malformed_2xx_response_healthy(self):
        factory = _SessionFactory(self._model())
        provider = _ProviderClient(
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "  "}}]},
                request=httpx.Request(
                    "POST", "https://provider.test/v1/chat/completions"
                ),
            )
        )

        async def run():
            with (
                patch.object(
                    ai_service,
                    "_caller_async_engine",
                    return_value=(object(), False),
                ),
                patch.object(
                    ai_service,
                    "_catalog_session_factory",
                    return_value=factory,
                ),
                patch.object(
                    ai_service.httpx,
                    "AsyncClient",
                    return_value=provider,
                ),
            ):
                return await ai_service.probe_model(
                    SimpleNamespace(), "example/model"
                )

        result = asyncio.run(run())
        self.assertEqual(result["health_status"], "unhealthy")
        self.assertEqual(result["last_error"], "provider returned an invalid response")
        self.assertTrue(provider.closed)

    def test_chat_rejects_malformed_2xx_response(self):
        provider = _ProviderClient(
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": ""}}]},
                request=httpx.Request(
                    "POST", "https://provider.test/v1/chat/completions"
                ),
            )
        )
        state_write = AsyncMock()

        async def run():
            with (
                patch.object(
                    ai_service,
                    "_caller_async_engine",
                    return_value=(object(), False),
                ),
                patch.object(
                    ai_service,
                    "_user_ai_snapshot",
                    new=AsyncMock(return_value=(True, False)),
                ),
                patch.object(
                    ai_service,
                    "_fallback_chain_from_engine",
                    new=AsyncMock(return_value=["example/model"]),
                ),
                patch.object(
                    ai_service,
                    "_model_snapshot",
                    new=AsyncMock(return_value={"model_id": "example/model"}),
                ),
                patch.object(
                    ai_service,
                    "_record_model_state",
                    new=state_write,
                ),
            ):
                with self.assertRaises(ai_service.AIProvidersExhaustedError):
                    await ai_service.chat_with_fallback(
                        SimpleNamespace(),
                        task="summary",
                        messages=[{"role": "user", "content": "hello"}],
                        client=provider,
                        user_id=1,
                    )

        asyncio.run(run())
        state_write.assert_awaited_once()
        self.assertEqual(
            state_write.await_args.kwargs["health_status"],
            "unhealthy",
        )

    def test_chat_fallback_does_not_touch_caller_transaction(self):
        model = self._model()
        factory = _SessionFactory(model)
        caller = SimpleNamespace(in_transaction=True, commits=0, rollbacks=0)
        provider = _ProviderClient(
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "done"}}],
                    "usage": {"total_tokens": 1},
                },
                request=httpx.Request(
                    "POST", "https://provider.test/v1/chat/completions"
                ),
            )
        )

        async def run():
            with (
                patch.object(
                    ai_service,
                    "_caller_async_engine",
                    return_value=(object(), False),
                ),
                patch.object(
                    ai_service,
                    "_user_ai_snapshot",
                    new=AsyncMock(return_value=(True, True)),
                ),
                patch.object(
                    ai_service,
                    "_fallback_chain_from_engine",
                    wraps=ai_service._fallback_chain_from_engine,
                ),
                patch.object(
                    ai_service,
                    "_catalog_session_factory",
                    return_value=factory,
                ),
            ):
                return await ai_service.chat_with_fallback(
                    caller,
                    task="summary",
                    messages=[{"role": "user", "content": "hello"}],
                    client=provider,
                    user_id=1,
                )

        result = asyncio.run(run())
        self.assertEqual(result["content"], "done")
        self.assertTrue(caller.in_transaction)
        self.assertEqual(caller.commits, 0)
        self.assertEqual(caller.rollbacks, 0)
        self.assertEqual(len(factory.sessions), 3)
        self.assertTrue(all(not session.active for session in factory.sessions))

    def test_register_commits_before_verification_provider(self):
        class Database:
            def __init__(self):
                self.user = None
                self.committed = False

            async def execute(self, _statement):
                return _Result(None)

            def add(self, user):
                self.user = user
                user.id = 41

            async def commit(self):
                self.committed = True

        database = Database()
        provider_observed = []

        async def send(user_id, email, username):
            provider_observed.append(
                (database.committed, user_id, email, username)
            )

        async def run():
            with (
                patch.object(
                    auth,
                    "enforce_auth_rate_limit",
                    new=AsyncMock(),
                ),
                patch.object(
                    auth,
                    "_send_user_verification",
                    new=AsyncMock(side_effect=send),
                ),
            ):
                return await auth.register(
                    auth.RegisterBody(
                        username="new-user",
                        email="new@example.com",
                        password="test-password",
                    ),
                    object(),
                    database,
                )

        result = asyncio.run(run())
        self.assertEqual(result["id"], 41)
        self.assertEqual(
            provider_observed,
            [(True, 41, "new@example.com", "new-user")],
        )

    def test_ai_base_url_rejects_insecure_remote_and_url_parts(self):
        invalid_urls = (
            "http://example.com/v1",
            "https://user:password@example.com/v1",
            "https://example.com/v1?tenant=one",
            "https://example.com/v1#fragment",
        )
        for ai_base_url in invalid_urls:
            with self.subTest(ai_base_url=ai_base_url):
                with self.assertRaisesRegex(ValueError, "CADENCE_AI_BASE_URL"):
                    Settings(
                        secret_key="a" * 40,
                        test_mode=False,
                        ai_base_url=ai_base_url,
                        _env_file=None,
                    )

        local = Settings(
            secret_key="a" * 40,
            test_mode=False,
            ai_base_url="http://127.0.0.1:8001/v1",
            _env_file=None,
        )
        self.assertEqual(local.ai_base_url, "http://127.0.0.1:8001/v1")

    def test_resend_releases_read_transaction_before_email_provider(self):
        class Database:
            def __init__(self):
                self.rolled_back = False
                self.commits = 0

            async def scalar(self, _statement):
                return SimpleNamespace(
                    id=7,
                    email="person@example.com",
                    username="person",
                    is_verified=False,
                )

            async def rollback(self):
                self.rolled_back = True

            async def commit(self):
                self.commits += 1

        database = Database()
        provider_observed = []

        async def send(*_args):
            provider_observed.append(database.rolled_back)

        async def run():
            with (
                patch.object(
                    auth,
                    "enforce_auth_rate_limit",
                    new=AsyncMock(),
                ),
                patch.object(
                    auth,
                    "_send_user_verification",
                    new=AsyncMock(side_effect=send),
                ),
            ):
                return await auth.resend_verification(
                    auth.ResendVerificationBody(email="person@example.com"),
                    object(),
                    database,
                )

        result = asyncio.run(run())
        self.assertIn("unverified account", result["message"])
        self.assertEqual(provider_observed, [True])
        self.assertEqual(database.commits, 0)

    def test_lifespan_disposes_both_engines(self):
        async def run():
            async_engine = SimpleNamespace(dispose=AsyncMock())
            sync_engine = SimpleNamespace(dispose=MagicMock())
            with (
                patch.object(
                    app_module.auth_rate_limiter,
                    "startup",
                    new=AsyncMock(),
                ),
                patch.object(
                    app_module.auth_rate_limiter,
                    "shutdown",
                    new=AsyncMock(),
                ),
                patch.object(app_module, "async_engine", async_engine),
                patch.object(app_module, "sync_engine", sync_engine),
            ):
                async with app_module.lifespan(None):
                    pass
                return async_engine.dispose, sync_engine.dispose

        async_dispose, sync_dispose = asyncio.run(run())
        async_dispose.assert_awaited_once()
        sync_dispose.assert_called_once()

    def test_backfill_reuses_one_owned_client_for_the_batch(self):
        class Result:
            def __init__(self, rows):
                self.rows = rows

            def all(self):
                return self.rows

        class Database:
            def __init__(self):
                self.calls = 0

            async def execute(self, _statement):
                self.calls += 1
                if self.calls == 1:
                    return Result(
                        [
                            (
                                SimpleNamespace(
                                    id=1,
                                    user_id=1,
                                    daily_note="first",
                                    date=date(2026, 8, 1),
                                ),
                                None,
                            ),
                            (
                                SimpleNamespace(
                                    id=2,
                                    user_id=1,
                                    daily_note="second",
                                    date=date(2026, 8, 2),
                                ),
                                None,
                            ),
                        ]
                    )
                return Result([])

            async def rollback(self):
                return None

        provider = _ProviderClient(httpx.Response(200))
        refresh = AsyncMock(return_value=True)

        async def run():
            with (
                patch.object(
                    embeddings.httpx,
                    "AsyncClient",
                    return_value=provider,
                ) as client_factory,
                patch.object(
                    embeddings,
                    "_sync_source_embedding",
                    new=refresh,
                ),
            ):
                result = await embeddings.backfill_embeddings(
                    Database(),
                    batch_size=2,
                )
                return result, client_factory

        result, client_factory = asyncio.run(run())
        self.assertEqual(result, {"attempted": 2, "refreshed": 2, "failed": 0})
        client_factory.assert_called_once()
        self.assertTrue(provider.closed)
        self.assertEqual(refresh.await_count, 2)
        self.assertIs(refresh.await_args_list[0].kwargs["client"], provider)
        self.assertIs(refresh.await_args_list[1].kwargs["client"], provider)


if __name__ == "__main__":
    unittest.main()

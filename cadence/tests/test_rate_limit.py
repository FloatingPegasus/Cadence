import asyncio
import os
import secrets
import unittest
from unittest.mock import AsyncMock, patch

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

from cadence.app.services.rate_limit import (
    auth_rate_limiter,
    enforce_auth_rate_limit,
    InMemoryRateLimiter,
    RateLimitUnavailable,
    RedisRateLimiter,
)
from cadence.app.config import Settings
from cadence.app.config import settings
from fastapi import HTTPException, Request


class MemoryRateLimiterTests(unittest.TestCase):
    def test_backend_configuration_is_explicit_and_strict(self) -> None:
        configured = Settings(
            secret_key="configuration-test-secret-key-32-characters",
            test_mode=False,
            auth_rate_limit_backend="redis",
            redis_url="redis://localhost:6379/0",
            frontend_base_url="https://app.example.com",
            cors_origins="https://app.example.com",
            _env_file=None,
        )
        self.assertEqual(configured.auth_rate_limit_backend, "redis")
        with self.assertRaises(ValueError):
            Settings(
                secret_key="configuration-test-secret-key-32-characters",
                test_mode=False,
                auth_rate_limit_backend="redis",
                redis_url="",
                _env_file=None,
            )
        with self.assertRaises(ValueError):
            Settings(
                secret_key="configuration-test-secret-key-32-characters",
                test_mode=False,
                auth_rate_limit_backend="redis",
                redis_url="http://localhost:6379",
                _env_file=None,
            )
        with self.assertRaises(ValueError):
            Settings(
                secret_key="configuration-test-secret-key-32-characters",
                test_mode=False,
                redis_connect_timeout_seconds=0,
                _env_file=None,
            )

    def test_ip_and_identity_dimensions_are_all_or_none(self) -> None:
        now = [100.0]
        limiter = InMemoryRateLimiter(clock=lambda: now[0])

        self.assertIsNone(
            limiter.allow(
                ["login:ip:one", "login:identity:blocked"],
                limit=1,
                window_seconds=60,
            )
        )
        retry_after = limiter.allow(
            ["login:ip:two", "login:identity:blocked"],
            limit=1,
            window_seconds=60,
        )
        self.assertGreater(retry_after or 0, 0)
        # The blocked identity request did not consume the new IP dimension.
        self.assertIsNone(
            limiter.allow(
                ["login:ip:two"],
                limit=1,
                window_seconds=60,
            )
        )

        now[0] = 161.0
        self.assertIsNone(
            limiter.allow(
                ["login:ip:one", "login:identity:blocked"],
                limit=1,
                window_seconds=60,
            )
        )

    def test_memory_retry_after_is_positive_and_expiry_is_deterministic(self) -> None:
        now = [10.0]
        limiter = InMemoryRateLimiter(clock=lambda: now[0])
        self.assertIsNone(
            limiter.retry_after("scope:key", limit=1, window_seconds=5)
        )
        self.assertEqual(
            limiter.retry_after("scope:key", limit=1, window_seconds=5),
            5,
        )
        now[0] = 15.0
        self.assertIsNone(
            limiter.retry_after("scope:key", limit=1, window_seconds=5)
        )


class RedisRateLimiterUnitTests(unittest.TestCase):
    def test_endpoint_enforcement_maps_backend_failure_to_generic_503(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/auth/login",
                "headers": [],
                "client": ("192.0.2.20", 1234),
                "scheme": "http",
            }
        )
        original_test_mode = settings.test_mode
        settings.test_mode = False
        try:
            with patch.object(
                auth_rate_limiter,
                "allow",
                new=AsyncMock(side_effect=RateLimitUnavailable("backend down")),
            ):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(
                        enforce_auth_rate_limit(
                            request,
                            scope="login",
                            identity="username:alpha",
                            limit=1,
                        )
                    )
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(
                raised.exception.detail,
                "Authentication protection is temporarily unavailable.",
            )
        finally:
            settings.test_mode = original_test_mode

    def test_startup_failure_does_not_fall_back(self) -> None:
        class DownClient:
            async def ping(self):
                raise ConnectionError("down")

            async def aclose(self):
                return None

        limiter = RedisRateLimiter(
            secret_key="unit-test-secret-key-32-characters-long",
            key_prefix="cadence-unit",
            client=DownClient(),
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(limiter.startup())

    def test_runtime_failure_is_reported_as_unavailable(self) -> None:
        class EvalDownClient:
            async def ping(self):
                return True

            async def eval(self, *args):
                raise ConnectionError("down during request")

            async def aclose(self):
                return None

        limiter = RedisRateLimiter(
            secret_key="unit-test-secret-key-32-characters-long",
            key_prefix="cadence-unit",
            client=EvalDownClient(),
        )

        async def exercise() -> None:
            await limiter.startup()
            try:
                with self.assertRaises(RateLimitUnavailable):
                    await limiter.allow(
                        "login",
                        [("ip", "192.0.2.1")],
                        limit=1,
                        window_seconds=60,
                    )
            finally:
                await limiter.close()

        asyncio.run(exercise())

    def test_malformed_redis_reply_fails_closed(self) -> None:
        class MalformedClient:
            async def ping(self):
                return True

            async def eval(self, *args):
                return {}

            async def aclose(self):
                return None

        limiter = RedisRateLimiter(
            secret_key="unit-test-secret-key-32-characters-long",
            key_prefix="cadence-unit",
            client=MalformedClient(),
        )

        async def exercise() -> None:
            await limiter.startup()
            try:
                with self.assertRaises(RateLimitUnavailable):
                    await limiter.allow(
                        "login",
                        [("ip", "192.0.2.2")],
                        limit=1,
                        window_seconds=60,
                    )
            finally:
                await limiter.close()

        asyncio.run(exercise())

    def test_redis_keys_hide_dimensions_and_share_scope_hash_tag(self) -> None:
        limiter = RedisRateLimiter(
            secret_key="unit-test-secret-key-32-characters-long",
            key_prefix="cadence-unit",
        )
        ip_key = limiter.key_for("login", "ip", "192.0.2.1")
        identity_key = limiter.key_for("login", "identity", "alpha@example.com")
        self.assertNotIn("192.0.2.1", ip_key)
        self.assertNotIn("alpha@example.com", identity_key)
        self.assertEqual(
            ip_key.split("{", 1)[1].split("}", 1)[0],
            identity_key.split("{", 1)[1].split("}", 1)[0],
        )


REDIS_URL = os.environ.get("CADENCE_TEST_REDIS_URL", "")


@unittest.skipUnless(
    REDIS_URL,
    "set CADENCE_TEST_REDIS_URL to run Redis rate-limit integration tests",
)
class RedisRateLimiterIntegrationTests(unittest.TestCase):
    def _run_with_limiters(self, exercise):
        prefix = f"cadence-test-{secrets.token_hex(8)}"

        async def run():
            first = RedisRateLimiter(
                redis_url=REDIS_URL,
                secret_key="integration-test-secret-key-32-characters",
                key_prefix=prefix,
            )
            second = RedisRateLimiter(
                redis_url=REDIS_URL,
                secret_key="integration-test-secret-key-32-characters",
                key_prefix=prefix,
            )
            await first.startup()
            await second.startup()
            try:
                return await exercise(first, second)
            finally:
                await first.close()
                await second.close()

        return asyncio.run(run())

    def test_quota_is_shared_across_limiter_instances(self) -> None:
        async def exercise(first, second):
            dimensions = [("ip", "192.0.2.10")]
            self.assertIsNone(
                await first.allow(
                    "login", dimensions, limit=1, window_seconds=60
                )
            )
            retry_after = await second.allow(
                "login", dimensions, limit=1, window_seconds=60
            )
            self.assertGreater(retry_after or 0, 0)

        self._run_with_limiters(exercise)

    def test_concurrent_requests_cannot_exceed_atomic_cap(self) -> None:
        async def exercise(first, _second):
            results = await asyncio.gather(
                *(
                    first.allow(
                        "register",
                        [("ip", "192.0.2.11")],
                        limit=3,
                        window_seconds=60,
                    )
                    for _ in range(24)
                )
            )
            self.assertEqual(sum(result is None for result in results), 3)
            self.assertTrue(all((result or 0) > 0 for result in results if result))

        self._run_with_limiters(exercise)

    def test_ip_and_identity_are_checked_all_or_none(self) -> None:
        async def exercise(first, _second):
            self.assertIsNone(
                await first.allow(
                    "resend",
                    [("identity", "blocked@example.com")],
                    limit=1,
                    window_seconds=60,
                )
            )
            retry_after = await first.allow(
                "resend",
                [("ip", "192.0.2.12"), ("identity", "blocked@example.com")],
                limit=1,
                window_seconds=60,
            )
            self.assertGreater(retry_after or 0, 0)
            self.assertIsNone(
                await first.allow(
                    "resend",
                    [("ip", "192.0.2.12")],
                    limit=1,
                    window_seconds=60,
                )
            )

        self._run_with_limiters(exercise)

    def test_retry_after_and_expiry(self) -> None:
        async def exercise(first, _second):
            dimensions = [("ip", "192.0.2.13")]
            self.assertIsNone(
                await first.allow(
                    "verify", dimensions, limit=1, window_seconds=1
                )
            )
            retry_after = await first.allow(
                "verify", dimensions, limit=1, window_seconds=1
            )
            self.assertGreater(retry_after or 0, 0)
            await asyncio.sleep(1.2)
            self.assertIsNone(
                await first.allow(
                    "verify", dimensions, limit=1, window_seconds=1
                )
            )

        self._run_with_limiters(exercise)

    def test_ttl_is_set_and_stale_members_are_removed(self) -> None:
        async def exercise(first, _second):
            stale_scope = "stale-members"
            stale_dimensions = [("ip", "192.0.2.14")]
            stale_key = first.key_for(stale_scope, "ip", "192.0.2.14")
            await first._client.zadd(stale_key, {"stale-event": 0})
            self.assertIsNone(
                await first.allow(
                    stale_scope,
                    stale_dimensions,
                    limit=1,
                    window_seconds=60,
                )
            )
            self.assertIsNone(await first._client.zscore(stale_key, "stale-event"))
            self.assertEqual(await first._client.zcard(stale_key), 1)
            stale_ttl = await first._client.ttl(stale_key)
            self.assertGreater(stale_ttl, 0)
            self.assertLessEqual(stale_ttl, 61)

            expiry_scope = "expiry"
            expiry_key = first.key_for(expiry_scope, "ip", "192.0.2.15")
            self.assertIsNone(
                await first.allow(
                    expiry_scope,
                    [("ip", "192.0.2.15")],
                    limit=1,
                    window_seconds=1,
                )
            )
            self.assertGreater(await first._client.ttl(expiry_key), 0)
            await asyncio.sleep(2.1)
            self.assertEqual(await first._client.exists(expiry_key), 0)

        self._run_with_limiters(exercise)


if __name__ == "__main__":
    unittest.main()

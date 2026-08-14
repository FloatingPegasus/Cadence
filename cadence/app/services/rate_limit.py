"""Authentication request limiting.

The memory backend is deliberately explicit and is suitable for local,
single-process development and tests. Deployments with more than one worker
or instance should select the Redis backend. Redis enforcement is one atomic
Lua operation, so a Redis outage fails closed with a temporary service error;
it never silently falls back to process-local state.
"""

from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from hashlib import sha256
from hmac import new as hmac_new
from inspect import isawaitable
from math import ceil
from secrets import token_hex
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from ..config import settings

try:  # Keep the memory/test path importable before dependencies are installed.
    from redis import asyncio as redis_asyncio
except ImportError:  # pragma: no cover - exercised by dependency installation
    redis_asyncio = None


class RateLimitUnavailable(RuntimeError):
    """The configured shared rate-limit backend cannot be reached."""


class InMemoryRateLimiter:
    """Thread-safe fixed-window event storage for one process.

    ``allow`` checks every supplied dimension before recording any event. This
    keeps the IP and identity dimensions all-or-none, matching Redis behavior.
    """

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._clock = clock

    def allow(
        self,
        keys: Sequence[str],
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        unique_keys = list(dict.fromkeys(keys))
        if not unique_keys:
            raise ValueError("at least one rate-limit key is required")
        now = self._clock()
        with self._lock:
            cutoff = now - window_seconds
            retry_after: int | None = None
            for key in unique_keys:
                events = self._events[key]
                while events and events[0] <= cutoff:
                    events.popleft()
                if len(events) >= limit:
                    remaining = max(1, ceil(window_seconds - (now - events[0])))
                    retry_after = max(retry_after or 0, remaining)
            if retry_after is not None:
                return retry_after

            for key in unique_keys:
                self._events[key].append(now)
            if len(self._events) > 4096:
                self._prune(now, window_seconds)
        return None

    def retry_after(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        """Compatibility helper for callers/tests that use one dimension."""

        return self.allow([key], limit=limit, window_seconds=window_seconds)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def _prune(self, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        stale = [
            key
            for key, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in stale:
            self._events.pop(key, None)


# All keys passed to this script share the same Redis Cluster hash tag. Redis
# TIME is the source of truth so instances with different local clocks cannot
# disagree about the sliding-window boundary.
REDIS_SLIDING_WINDOW_SCRIPT = """
local server_time = redis.call('TIME')
local now_ms = tonumber(server_time[1]) * 1000 + math.floor(tonumber(server_time[2]) / 1000)
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local event_id = ARGV[3]
local cutoff = now_ms - window_ms
local retry_after_ms = 0
local blocked = false
local ttl_seconds = math.ceil(window_ms / 1000) + 1

for _, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
    redis.call('EXPIRE', key, ttl_seconds)
    if redis.call('ZCARD', key) >= limit then
        local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        if first[2] then
            local remaining = tonumber(first[2]) + window_ms - now_ms
            if remaining > retry_after_ms then
                retry_after_ms = remaining
            end
        end
        blocked = true
    end
end

if blocked then
    return {0, math.max(1, math.ceil(retry_after_ms / 1000))}
end

for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, now_ms, event_id)
    redis.call('EXPIRE', key, ttl_seconds)
end
return {1, 0}
"""


class RedisRateLimiter:
    """Atomic sliding-window limiter backed by redis-py's asyncio client."""

    def __init__(
        self,
        redis_url: str | None = None,
        secret_key: str | None = None,
        key_prefix: str | None = None,
        redis_connect_timeout_seconds: float | None = None,
        redis_socket_timeout_seconds: float | None = None,
        *,
        client=None,
    ) -> None:
        self.redis_url = redis_url if redis_url is not None else settings.redis_url
        signing_secret = secret_key if secret_key is not None else settings.secret_key
        self.key_prefix = (
            key_prefix if key_prefix is not None else settings.redis_key_prefix
        )
        self.redis_connect_timeout_seconds = (
            redis_connect_timeout_seconds
            if redis_connect_timeout_seconds is not None
            else settings.redis_connect_timeout_seconds
        )
        self.redis_socket_timeout_seconds = (
            redis_socket_timeout_seconds
            if redis_socket_timeout_seconds is not None
            else settings.redis_socket_timeout_seconds
        )
        self._hmac_key = hmac_new(
            signing_secret.encode("utf-8"),
            b"cadence-rate-limit-key-v1",
            sha256,
        ).digest()
        self._client = client
        self._started = False

    async def startup(self) -> None:
        if self._client is None:
            if redis_asyncio is None:
                raise RuntimeError(
                    "Redis rate limiting requires the redis package to be installed"
                )
            if not self.redis_url:
                raise RuntimeError("Redis rate limiting requires CADENCE_REDIS_URL")
            self._client = redis_asyncio.Redis.from_url(
                self.redis_url,
                decode_responses=False,
                socket_connect_timeout=self.redis_connect_timeout_seconds,
                socket_timeout=self.redis_socket_timeout_seconds,
            )
        try:
            await self._client.ping()
        except Exception as error:
            await self.close()
            raise RuntimeError("Redis rate-limit backend is unavailable") from error
        self._started = True

    async def close(self) -> None:
        client = self._client
        self._client = None
        self._started = False
        if client is None:
            return
        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if close is None:
            return
        try:
            result = close()
            if isawaitable(result):
                await result
        except Exception:
            # Closing is best effort and must not hide an original failure.
            return

    async def shutdown(self) -> None:
        await self.close()

    def key_for(self, scope: str, dimension: str, value: str) -> str:
        """Build a non-reversible Redis key without exposing user data."""

        scope_digest = self._digest("scope", scope)
        value_digest = self._digest("dimension", dimension, value)
        return f"{self.key_prefix}:{{{scope_digest}}}:{value_digest}"

    def _digest(self, *parts: str) -> str:
        message = b"\x00".join(part.encode("utf-8") for part in parts)
        return hmac_new(self._hmac_key, message, sha256).hexdigest()

    async def allow(
        self,
        scope: str,
        dimensions: Sequence[tuple[str, str]],
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        if not self._started or self._client is None:
            raise RateLimitUnavailable("Redis rate-limit backend is not ready")
        keys = list(
            dict.fromkeys(
                self.key_for(scope, dimension, value)
                for dimension, value in dimensions
            )
        )
        if not keys:
            raise ValueError("at least one rate-limit dimension is required")
        try:
            result = await self._client.eval(
                REDIS_SLIDING_WINDOW_SCRIPT,
                len(keys),
                *keys,
                limit,
                window_seconds * 1000,
                token_hex(16),
            )
        except Exception as error:
            raise RateLimitUnavailable(
                "Redis rate-limit backend failed during enforcement"
            ) from error
        try:
            if len(result) != 2:
                raise ValueError("unexpected Redis result length")
            allowed = int(result[0])
            retry_after = int(result[1])
            if allowed not in {0, 1}:
                raise ValueError("unexpected Redis allow flag")
            if retry_after < 0 or (allowed == 0 and retry_after == 0):
                raise ValueError("unexpected Redis retry-after value")
            if allowed == 1 and retry_after != 0:
                raise ValueError("allowed Redis result must have zero retry-after")
        except Exception as error:
            raise RateLimitUnavailable(
                "Redis rate-limit backend returned an invalid result"
            ) from error
        if allowed:
            return None
        return max(1, retry_after)


class AuthRateLimiter:
    """Select the explicitly configured backend and own its lifecycle."""

    def __init__(self) -> None:
        self._memory = InMemoryRateLimiter()
        self._redis: RedisRateLimiter | None = None

    @property
    def backend(self) -> str:
        return settings.auth_rate_limit_backend

    async def startup(self) -> None:
        if settings.auth_rate_limit_backend == "redis":
            if self._redis is None or (
                self._redis.redis_url != settings.redis_url
                or self._redis.key_prefix != settings.redis_key_prefix
                or self._redis.redis_connect_timeout_seconds
                != settings.redis_connect_timeout_seconds
                or self._redis.redis_socket_timeout_seconds
                != settings.redis_socket_timeout_seconds
            ):
                if self._redis is not None:
                    await self._redis.close()
                self._redis = RedisRateLimiter(
                    redis_url=settings.redis_url,
                    secret_key=settings.secret_key,
                    key_prefix=settings.redis_key_prefix,
                    redis_connect_timeout_seconds=settings.redis_connect_timeout_seconds,
                    redis_socket_timeout_seconds=settings.redis_socket_timeout_seconds,
                )
            await self._redis.startup()
            return
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    def clear(self) -> None:
        """Clear the process-local backend (useful for tests and development)."""

        self._memory.clear()

    async def allow(
        self,
        scope: str,
        dimensions: Sequence[tuple[str, str]],
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        if settings.auth_rate_limit_backend == "redis":
            if self._redis is None:
                raise RateLimitUnavailable("Redis rate-limit backend is not ready")
            return await self._redis.allow(
                scope,
                dimensions,
                limit=limit,
                window_seconds=window_seconds,
            )
        keys = [
            f"{scope}:{dimension}:{value}" for dimension, value in dimensions
        ]
        return self._memory.allow(
            keys,
            limit=limit,
            window_seconds=window_seconds,
        )


auth_rate_limiter = AuthRateLimiter()


def request_client_key(request: Request) -> str:
    """Return the direct peer address, never an attacker-controlled header."""

    return request.client.host if request.client else "unknown"


async def enforce_auth_rate_limit(
    request: Request,
    *,
    scope: str,
    identity: str | None,
    limit: int,
    window_seconds: int | None = None,
) -> None:
    if settings.test_mode:
        return
    window = window_seconds or settings.auth_rate_limit_window_seconds
    dimensions = [("ip", request_client_key(request))]
    if identity:
        dimensions.append(("identity", identity))
    try:
        retry_after = await auth_rate_limiter.allow(
            scope,
            dimensions,
            limit=limit,
            window_seconds=window,
        )
    except RateLimitUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication protection is temporarily unavailable.",
        ) from error
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

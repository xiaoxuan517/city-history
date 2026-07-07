from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import Request, status
from redis import Redis
from redis.exceptions import RedisError

from app.api.errors import ApiError
from app.config.settings import settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, float]] = {}

    def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        count, expires_at = self._counters.get(key, (0, now + window_seconds))
        if now >= expires_at:
            count = 0
            expires_at = now + window_seconds

        count += 1
        self._counters[key] = (count, expires_at)
        remaining = max(limit - count, 0)
        retry_after = max(int(expires_at - now), 1)
        return RateLimitResult(allowed=count <= limit, remaining=remaining, retry_after_seconds=retry_after)


class RedisRateLimiter:
    def __init__(self, redis_client: Redis, *, fallback: InMemoryRateLimiter | None = None) -> None:
        self._redis = redis_client
        self._fallback = fallback or InMemoryRateLimiter()

    def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        try:
            count = int(self._redis.incr(key))
            if count == 1:
                self._redis.expire(key, window_seconds)
            ttl = self._redis.ttl(key)
            retry_after = ttl if ttl and ttl > 0 else window_seconds
            remaining = max(limit - count, 0)
            return RateLimitResult(allowed=count <= limit, remaining=remaining, retry_after_seconds=retry_after)
        except RedisError:
            return self._fallback.check(key=key, limit=limit, window_seconds=window_seconds)


_memory_limiter = InMemoryRateLimiter()
_redis_limiter: RedisRateLimiter | None = None


def get_rate_limiter() -> RedisRateLimiter | InMemoryRateLimiter:
    global _redis_limiter
    if _redis_limiter is None:
        _redis_limiter = RedisRateLimiter(Redis.from_url(settings.redis_url, decode_responses=True), fallback=_memory_limiter)
    return _redis_limiter


def _client_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "").strip()
    if authorization:
        return f"auth:{authorization}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def check_rate_limit(
    request: Request,
    limiter: RedisRateLimiter | InMemoryRateLimiter | None = None,
) -> None:
    if not settings.rate_limit_enabled:
        return

    state_limiter = getattr(request.app.state, "rate_limiter", None)
    resolved_limiter = limiter or state_limiter or get_rate_limiter()
    key = f"rate_limit:{_client_key(request)}"
    result = resolved_limiter.check(
        key=key,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if result.allowed:
        return

    raise ApiError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="rate_limit_exceeded",
        message="Too many requests",
        headers={"Retry-After": str(result.retry_after_seconds)},
    )


def enforce_rate_limit(request: Request) -> None:
    check_rate_limit(request)

"""Rate limiting middleware and dependencies for FastAPI endpoints.

Provides sliding-window rate limiting with dual backends:
1. Redis-backed sliding window via sorted sets (when REDIS_URL is configured).
2. Thread-safe in-memory sliding window deque fallback (for standalone dev/testing).
"""

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Optional, Tuple
from fastapi import HTTPException, Request, status
from app.core.config import settings

logger = logging.getLogger("masscommai.rate_limiter")


class MemoryRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._storage = defaultdict(deque)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if an operation is allowed under the rate limit.
        Returns:
            Tuple[bool, int]: (allowed, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            q = self._storage[key]
            # Prune timestamps older than cutoff
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) < limit:
                q.append(now)
                return True, 0

            # Calculate retry after based on the oldest timestamp
            oldest = q[0]
            retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
            return False, retry_after

    def reset(self) -> None:
        """Clear all stored rate limit history."""
        with self._lock:
            self._storage.clear()


class RedisRateLimiter:
    """Distributed Redis sliding window rate limiter using atomic Lua scripting."""

    # Atomic Lua script executing sliding window rate limit evaluation in a single Redis transaction
    LUA_SLIDING_WINDOW = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local member = ARGV[4]
    local cutoff = now - window

    -- 1. Prune expired entries older than cutoff
    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

    -- 2. Count current active requests in sliding window
    local current_count = redis.call('ZCARD', key)

    if current_count < limit then
        -- Within limit: atomically add request and set TTL
        redis.call('ZADD', key, now, member)
        redis.call('EXPIRE', key, window + 5)
        return {1, 0}
    else
        -- Exceeded limit: calculate retry_after from oldest entry
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = window
        if oldest and #oldest >= 2 then
            local oldest_ts = tonumber(oldest[2])
            retry_after = math.max(1, math.floor(window - (now - oldest_ts)) + 1)
        end
        return {0, retry_after}
    end
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._client = None
        self._script = None

    def _get_client(self):
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
                self._script = self._client.register_script(self.LUA_SLIDING_WINDOW)
            except Exception as exc:
                logger.warning("Failed to initialize Redis rate limit client: %s", exc)
                self._client = None
                self._script = None
                return None
        return self._client

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        client = self._get_client()
        if client is None or self._script is None:
            logger.warning("Redis client unavailable; falling back to in-memory rate limiter")
            return _memory_limiter.is_allowed(key, limit, window_seconds)

        now = time.time()
        redis_key = f"masscomm:rl:{key}"
        # Unique member prevents ZSET key collision even under identical microsecond timestamps
        unique_member = f"{now}:{uuid.uuid4().hex[:8]}"

        try:
            result = self._script(
                keys=[redis_key],
                args=[now, window_seconds, limit, unique_member],
            )
            allowed = bool(result[0])
            retry_after = int(result[1])
            return allowed, retry_after
        except Exception as exc:
            logger.warning("Redis rate limit operation failed (%s); falling back to in-memory limiter", exc)
            self._client = None  # Reset client so next request re-establishes connection
            self._script = None
            return _memory_limiter.is_allowed(key, limit, window_seconds)

    def reset(self) -> None:
        """Clear all stored rate limit keys in Redis matching masscomm:rl:*."""
        client = self._get_client()
        if client is not None:
            try:
                keys = list(client.scan_iter(match="masscomm:rl:*", count=100))
                if keys:
                    client.delete(*keys)
            except Exception as exc:
                logger.warning("Failed to reset Redis rate limit keys: %s", exc)

    def close(self) -> None:
        """Close Redis connection and release pool."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("Error closing Redis client: %s", exc)
            finally:
                self._client = None
                self._script = None


# Global limiter instances
_memory_limiter = MemoryRateLimiter()
_redis_limiter = RedisRateLimiter(settings.REDIS_URL) if settings.REDIS_URL else None


def get_rate_limiter_backend():
    """Return active rate limiter backend (Redis if configured, else Memory)."""
    if settings.REDIS_URL:
        global _redis_limiter
        if _redis_limiter is None:
            _redis_limiter = RedisRateLimiter(settings.REDIS_URL)
        return _redis_limiter
    return _memory_limiter


def reset_rate_limiters() -> None:
    """Helper for test suites to reset memory and Redis limiter counters."""
    _memory_limiter.reset()
    if _redis_limiter is not None:
        _redis_limiter.reset()


def close_rate_limiters() -> None:
    """Close active rate limiter connections on application shutdown."""
    global _redis_limiter
    if _redis_limiter is not None:
        _redis_limiter.close()


class RateLimiter:
    """
    FastAPI dependency enforcing a sliding window request rate limit.

    Usage:
        @router.post("/login", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
    """

    def __init__(self, times: int, seconds: int = 60, prefix: str = "rl") -> None:
        self.times = times
        self.seconds = seconds
        self.prefix = prefix

    def _get_client_identifier(self, request: Request) -> str:
        # Check X-Forwarded-For header for reverse proxy environments
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        # If user is authenticated, append user identifier for per-user rate limiting
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token_snippet = auth_header[7:23]
            return f"{client_ip}:{token_snippet}"

        return client_ip

    async def __call__(self, request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        identifier = self._get_client_identifier(request)
        rate_key = f"{self.prefix}:{request.url.path}:{identifier}"
        backend = get_rate_limiter_backend()

        allowed, retry_after = backend.is_allowed(
            key=rate_key,
            limit=self.times,
            window_seconds=self.seconds,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for client %s on %s. Limit: %d req/%ds",
                identifier,
                request.url.path,
                self.times,
                self.seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.times} requests allowed per {self.seconds} seconds. Please retry in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

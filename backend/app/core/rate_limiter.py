"""Rate limiting middleware and dependencies for FastAPI endpoints.

Provides sliding-window rate limiting with dual backends:
1. Redis-backed sliding window via sorted sets (when REDIS_URL is configured).
2. Thread-safe in-memory sliding window deque fallback (for standalone dev/testing).
"""

import logging
import threading
import time
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
    """Distributed Redis sliding window rate limiter using sorted sets."""

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._client = None

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
            except Exception as exc:
                logger.warning("Failed to initialize Redis rate limit client: %s", exc)
                return None
        return self._client

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        client = self._get_client()
        if client is None:
            return True, 0  # Fail open if Redis cannot be contacted

        now = time.time()
        cutoff = now - window_seconds
        redis_key = f"masscomm:rl:{key}"

        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            results = pipe.execute()

            current_count = results[1]
            oldest_entries = results[2]

            if current_count < limit:
                pipe = client.pipeline()
                pipe.zadd(redis_key, {str(now): now})
                pipe.expire(redis_key, window_seconds + 5)
                pipe.execute()
                return True, 0

            # Limit exceeded; calculate retry_after
            if oldest_entries:
                oldest_ts = float(oldest_entries[0][1])
                retry_after = max(1, int(window_seconds - (now - oldest_ts)) + 1)
            else:
                retry_after = window_seconds

            return False, retry_after
        except Exception as exc:
            logger.warning("Redis rate limit operation failed, failing open: %s", exc)
            return True, 0


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
    """Helper for test suites to reset memory limiter counters."""
    _memory_limiter.reset()


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

# src/api/rate_limiter.py
"""Sliding-window rate limiter for API endpoints.

Two backends, selected at startup:
- Redis-backed (multi-worker safe): active when REDIS_RATE_LIMIT_URL is set.
  Uses a Lua script for atomic ZREMRANGEBYSCORE + ZCARD + ZADD on a sorted-set
  key per (limit_key, client_key) pair.
- In-process fallback: single-process only; used when Redis is not configured.

On Redis connectivity failure the limiter fails open (allows the request) and
logs a WARNING. The in-process account-lockout mechanism in AuthRunner still
provides brute-force protection in that scenario.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import HTTPException, status

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "login": (10, 60),
    "register": (5, 60),
    "refresh": (60, 3600),
    "password_reset": (3, 3600),
}

# ---------------------------------------------------------------------------
# In-process backend
# ---------------------------------------------------------------------------

_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_in_process(key: str, max_calls: int, window: int) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[key]
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= max_calls:
            return False
        bucket.append(now)
        return True


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------

# Atomic sliding-window via sorted set: remove expired, count, add if under limit.
_LUA_SLIDING_WINDOW = """
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    return 0
end
redis.call('ZADD', KEYS[1], now, member)
redis.call('EXPIRE', KEYS[1], math.ceil(window) + 1)
return 1
"""

_redis_client: Any = None
_redis_init_attempted: bool = False


def _get_redis() -> Any:
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    url = settings.REDIS_RATE_LIMIT_URL
    if not url:
        return None
    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        logger.info("Rate limiter: Redis backend initialised")
    except Exception as exc:
        logger.warning(
            "Rate limiter: Redis init failed (%s); falling back to in-process", exc
        )
    return _redis_client


async def _check_redis_window(
    client: Any, key: str, max_calls: int, window: int
) -> bool | None:
    """Return True=allowed, False=limited, None=Redis error (caller fails open)."""
    try:
        now = time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
        result = await client.eval(
            _LUA_SLIDING_WINDOW,
            1,
            key,
            str(now),
            str(window),
            str(max_calls),
            member,
        )
        return bool(result)
    except Exception as exc:
        logger.warning("Rate limiter: Redis error (%s); failing open", exc)
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


# ID: 815de2cf-2cca-49b3-a37a-5b68660b04e3
async def check_rate(client_key: str, limit_key: str) -> None:
    """Check and record a rate-limited request. Raises HTTP 429 when over limit.

    Uses the Redis backend when REDIS_RATE_LIMIT_URL is configured, otherwise
    falls back to an in-process sliding window.
    """
    max_calls, window = _RATE_LIMITS[limit_key]
    namespaced_key = f"core:rl:{limit_key}:{client_key}"

    redis = _get_redis()
    if redis is not None:
        allowed = await _check_redis_window(redis, namespaced_key, max_calls, window)
        if allowed is None:
            return
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        return

    if not _check_in_process(namespaced_key, max_calls, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

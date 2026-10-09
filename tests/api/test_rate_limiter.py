# tests/api/test_rate_limiter.py
"""Tests for api.rate_limiter — both backends and fail-open behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_module_state() -> None:
    """Reset singleton state between tests so backends can be re-initialised."""
    import api.rate_limiter as rl

    rl._redis_client = None
    rl._redis_init_attempted = False
    rl._rate_buckets.clear()


# ---------------------------------------------------------------------------
# In-process backend
# ---------------------------------------------------------------------------


class TestInProcessBackend:
    def setup_method(self) -> None:
        _reset_module_state()

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self) -> None:
        from api.rate_limiter import check_rate

        # login limit: 10 per 60s — 10 calls must succeed
        with patch("api.rate_limiter.settings") as mock_settings:
            mock_settings.REDIS_RATE_LIMIT_URL = None
            for _ in range(10):
                await check_rate("127.0.0.1", "login")

    @pytest.mark.asyncio
    async def test_raises_429_when_limit_exceeded(self) -> None:
        from api.rate_limiter import check_rate

        with patch("api.rate_limiter.settings") as mock_settings:
            mock_settings.REDIS_RATE_LIMIT_URL = None
            # Exhaust the register limit (5 per 60s)
            for _ in range(5):
                await check_rate("10.0.0.1", "register")

            with pytest.raises(HTTPException) as exc_info:
                await check_rate("10.0.0.1", "register")

            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_keys_are_independent(self) -> None:
        from api.rate_limiter import check_rate

        with patch("api.rate_limiter.settings") as mock_settings:
            mock_settings.REDIS_RATE_LIMIT_URL = None
            # Exhaust register limit for ip-A
            for _ in range(5):
                await check_rate("1.2.3.4", "register")

            # ip-B should still be allowed (separate bucket)
            await check_rate("5.6.7.8", "register")


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class TestRedisBackend:
    def setup_method(self) -> None:
        _reset_module_state()

    def _make_mock_redis(self, eval_return: int) -> AsyncMock:
        client = AsyncMock()
        client.eval = AsyncMock(return_value=eval_return)
        return client

    @pytest.mark.asyncio
    async def test_redis_allows_when_script_returns_1(self) -> None:
        from api.rate_limiter import check_rate

        mock_client = self._make_mock_redis(eval_return=1)
        with (
            patch("api.rate_limiter.settings") as mock_settings,
            patch("api.rate_limiter._get_redis", return_value=mock_client),
        ):
            mock_settings.REDIS_RATE_LIMIT_URL = "redis://localhost:6379"
            await check_rate("127.0.0.1", "login")

        mock_client.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_raises_429_when_script_returns_0(self) -> None:
        from api.rate_limiter import check_rate

        mock_client = self._make_mock_redis(eval_return=0)
        with patch("api.rate_limiter._get_redis", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await check_rate("127.0.0.1", "login")

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_redis_error_fails_open(self) -> None:
        """When Redis raises, the limiter fails open (allows the request)."""
        from api.rate_limiter import check_rate

        error_client = AsyncMock()
        error_client.eval = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("api.rate_limiter._get_redis", return_value=error_client):
            # Must NOT raise — fail-open
            await check_rate("127.0.0.1", "login")

    @pytest.mark.asyncio
    async def test_lua_script_called_with_correct_key_structure(self) -> None:
        from api.rate_limiter import check_rate

        mock_client = self._make_mock_redis(eval_return=1)
        with patch("api.rate_limiter._get_redis", return_value=mock_client):
            await check_rate("192.168.1.1", "register")

        call_args = mock_client.eval.call_args
        # Second positional arg is the key (KEYS[1])
        assert call_args.args[2] == "core:rl:register:192.168.1.1"


# ---------------------------------------------------------------------------
# Initialisation — no Redis URL
# ---------------------------------------------------------------------------


class TestInitialisation:
    def setup_method(self) -> None:
        _reset_module_state()

    def test_get_redis_returns_none_when_url_not_set(self) -> None:
        from api.rate_limiter import _get_redis

        with patch("api.rate_limiter.settings") as mock_settings:
            mock_settings.REDIS_RATE_LIMIT_URL = None
            client = _get_redis()

        assert client is None

    def test_get_redis_returns_none_on_from_url_failure(self) -> None:
        import redis.asyncio as aioredis

        from api.rate_limiter import _get_redis

        with (
            patch("api.rate_limiter.settings") as mock_settings,
            patch.object(aioredis, "from_url", side_effect=RuntimeError("bad url")),
        ):
            mock_settings.REDIS_RATE_LIMIT_URL = "redis://bad-host:9999"
            client = _get_redis()

        assert client is None

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.rate_limiter import check_rate


@pytest.mark.asyncio
# ID: 24db38e5-4a0f-4bce-a9c8-10bc76b5b827
async def test_check_rate() -> None:
    mock_redis = MagicMock()
    allowed_mock = AsyncMock(return_value=True)

    with (
        patch("api.rate_limiter._get_redis", return_value=mock_redis),
        patch("api.rate_limiter._check_redis_window", allowed_mock),
    ):
        await check_rate("client-1", "login")

    allowed_mock.assert_awaited_once_with(mock_redis, "core:rl:login:client-1", 10, 60)

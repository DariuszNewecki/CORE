from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.quality_client import QualityClient


@pytest.mark.asyncio
# ID: 8dc2b18c-e43f-47f9-b319-d159e8d088a6
async def test_QualityClient_quality_tests():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "tests": []})
    client = QualityClient(facade)

    result = await client.quality_tests(path="tests/unit")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/quality/tests",
        json={"path": "tests/unit"},
    )
    assert result == {"status": "ok", "tests": []}

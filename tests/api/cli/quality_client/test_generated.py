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


import asyncio


# ID: dce2dfe1-2791-4c24-8f37-6c9236a1feb2
def test_QualityClient_quality_lint():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "issues": []})

    client = QualityClient(facade)

    result = asyncio.run(client.quality_lint(fix=True))

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/quality/lint",
        json={"fix": True},
    )
    assert result == {"status": "ok", "issues": []}

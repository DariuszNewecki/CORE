from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.refactor_client import RefactorClient


@pytest.mark.asyncio
# ID: 0fdfed91-30c1-4bb1-a678-ba38ad90bd13
async def test_RefactorClient_poll_refactor_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(
        return_value={"status": "succeeded", "id": "run-123"}
    )

    client = RefactorClient(facade)

    result = await client.poll_refactor_run("run-123", timeout_seconds=42.0)

    assert result == {"status": "succeeded", "id": "run-123"}
    facade._poll_at_path.assert_awaited_once_with(
        "/v1/refactor/runs/run-123", timeout_seconds=42.0
    )


import asyncio


# ID: 2a60d2bd-61ab-4907-a8ba-3d298f491650
def test_RefactorClient_get_refactor_run():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "completed"})
    client = RefactorClient(facade)

    result = asyncio.run(client.get_refactor_run("run-123"))

    facade._request.assert_awaited_once_with("GET", "/v1/refactor/runs/run-123")
    assert result == {"id": "run-123", "status": "completed"}

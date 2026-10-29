from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from api.cli.sync_client import SyncClient


# ID: 0db4652b-8e6c-4b22-ae58-ea4d0098d5c5
def test_SyncClient_poll_sync_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(return_value={"status": "completed"})
    client = SyncClient(facade)

    result = asyncio.run(client.poll_sync_run("run-123", timeout_seconds=42.0))

    assert result == {"status": "completed"}
    facade._poll_at_path.assert_awaited_once_with(
        "/v1/sync/runs/run-123", timeout_seconds=42.0
    )



import pytest


@pytest.mark.asyncio
# ID: 2f7f39d7-531f-4359-b9de-afa3833d21aa
async def test_SyncClient_get_sync_run():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "ok"})
    client = SyncClient(facade)

    result = await client.get_sync_run("run-123")

    facade._request.assert_awaited_once_with("GET", "/v1/sync/runs/run-123")
    assert result == {"id": "run-123", "status": "ok"}

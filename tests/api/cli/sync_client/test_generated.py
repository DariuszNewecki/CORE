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


# ID: aef6465a-ce7c-44ba-b121-19d1b23c6096
async def test_SyncClient_sync_dev_sync() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "applied": 3})
    client = SyncClient(facade)

    result = await client.sync_dev_sync(write=True, target="dev", requested_by="tester")

    assert result == {"ok": True, "applied": 3}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/sync/dev-sync",
        json={"write": True, "target": "dev", "requested_by": "tester"},
    )


import pytest


@pytest.mark.asyncio
# ID: c71007a7-5c91-4bc2-bace-57dc450133d1
async def test_SyncClient_sync_code_vectors():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "count": 3})

    client = SyncClient(facade)

    result = await client.sync_code_vectors(
        write=True,
        target="pkg",
        requested_by="tester",
        force=True,
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/sync/code-vectors",
        json={
            "write": True,
            "target": "pkg",
            "requested_by": "tester",
            "force": True,
        },
    )
    assert result == {"status": "ok", "count": 3}





# ID: 358b3a40-b016-415a-9a78-77b0f52594fb
async def test_SyncClient_sync_vectors():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "synced": 3})

    client = SyncClient(facade)

    result = await client.sync_vectors(
        write=True, target="vectors", requested_by="tester"
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/sync/vectors",
        json={"write": True, "target": "vectors", "requested_by": "tester"},
    )
    assert result == {"status": "ok", "synced": 3}

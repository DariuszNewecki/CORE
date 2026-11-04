from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.fix_client import FixClient


# ID: 90a26e0a-e70c-4c9b-afc0-d21f72e9a1f8
async def test_FixClient_get_fix_run():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "completed"})

    client = FixClient(facade)

    result = await client.get_fix_run("run-123")

    facade._request.assert_awaited_once_with("GET", "/v1/fix/runs/run-123")
    assert result == {"id": "run-123", "status": "completed"}


import pytest


@pytest.mark.asyncio
# ID: ea84df0f-d418-4fac-b7e7-922b23d81526
async def test_FixClient_fix_ir():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "path": "x.yaml"})

    client = FixClient(facade)

    result = await client.fix_ir("triage")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/fix/ir",
        json={"kind": "triage"},
    )
    assert result == {"ok": True, "path": "x.yaml"}

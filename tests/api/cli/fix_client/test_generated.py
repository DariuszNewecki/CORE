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

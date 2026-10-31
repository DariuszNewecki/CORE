from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.findings_client import FindingsClient


@pytest.mark.asyncio
# ID: 41895fb5-5c2f-43cd-a2a2-ddb440e075a8
async def test_FindingsClient_resolve() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"resolved": True, "actor": "server"})

    client = FindingsClient(facade)

    result = await client.resolve("entry-123", "duplicate")

    facade._request.assert_awaited_once_with(
        "POST", "/v1/findings/entry-123/resolve", json={"reason": "duplicate"}
    )
    assert result == {"resolved": True, "actor": "server"}

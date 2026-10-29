from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.cli.daemon_client import DaemonClient


@pytest.mark.asyncio
# ID: a058a329-fd6d-4088-b8e0-704a52965c75
async def test_DaemonClient_daemon_stop():
    facade = AsyncMock()
    facade._request = AsyncMock(return_value={"status": "ok"})
    client = DaemonClient(facade)

    result = await client.daemon_stop()

    assert result == {"status": "ok"}
    facade._request.assert_awaited_once_with("POST", "/v1/daemon/stop", json={})

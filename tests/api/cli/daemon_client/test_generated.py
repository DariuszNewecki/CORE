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


import asyncio
from unittest.mock import MagicMock


# ID: 91e2d660-c3b8-4251-912b-67430c743314
def test_DaemonClient_daemon_start():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "started"})

    client = DaemonClient(facade)

    result = asyncio.run(client.daemon_start())

    assert result == {"status": "started"}
    facade._request.assert_awaited_once_with("POST", "/v1/daemon/start", json={})


import pytest


@pytest.mark.asyncio
# ID: 609fe4b0-d30b-4454-a879-b985e81c20dd
async def test_DaemonClient_daemon_status():
    expected = {"alive": True, "workers": [{"name": "w1", "healthy": True}]}

    facade = MagicMock()
    facade._request = AsyncMock(return_value=expected)

    client = DaemonClient(facade)

    result = await client.daemon_status()

    assert result == expected
    facade._request.assert_awaited_once_with("GET", "/v1/daemon/status")



import pytest


@pytest.mark.asyncio
# ID: e6c72f09-5d19-435d-a353-fbe52671e1ed
async def test_DaemonClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok"})

    client = DaemonClient(facade)

    result = await client.daemon_status()
    assert result == {"status": "ok"}
    facade._request.assert_awaited_once_with("GET", "/v1/daemon/status")

    result = await client.daemon_start()
    assert result == {"status": "ok"}
    facade._request.assert_awaited_with("POST", "/v1/daemon/start", json={})

    result = await client.daemon_stop()
    assert result == {"status": "ok"}
    facade._request.assert_awaited_with("POST", "/v1/daemon/stop", json={})

    assert facade._request.await_count == 3

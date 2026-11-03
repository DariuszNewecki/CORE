from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.project_client import ProjectClient


@pytest.mark.asyncio
# ID: aaf0877a-74cb-4b2c-8b81-055db4ad51b8
async def test_ProjectClient_scout():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"signals": [], "rules": []})

    client = ProjectClient(facade)

    result = await client.scout("/some/path", reset=True)

    assert result == {"signals": [], "rules": []}
    facade._request.assert_awaited_once_with(
        "POST", "/v1/project/scout", json={"path": "/some/path", "reset": True}
    )

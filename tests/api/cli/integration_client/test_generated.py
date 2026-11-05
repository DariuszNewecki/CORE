from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.integration_client import IntegrationClient


# ID: 110aba85-16e0-4382-9866-453c8383a673
async def test_IntegrationClient_lint() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"passed": True})

    client = IntegrationClient(facade)

    result = await client.lint()

    facade._request.assert_awaited_once_with("POST", "/v1/lint", timeout=300.0)
    assert result == {"passed": True}

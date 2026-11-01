from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.secrets_client import SecretsClient


@pytest.mark.asyncio
# ID: 7c1986e4-b3b3-452a-849c-8a47dfb245d3
async def test_SecretsClient_get_secret():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"key": "db_password", "value": "s3cr3t"})

    client = SecretsClient(facade)

    result = await client.get_secret("db_password", show=True)

    assert result == {"key": "db_password", "value": "s3cr3t"}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/secrets/db_password", params={"show": True}
    )

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


import pytest


@pytest.mark.asyncio
# ID: 5a85f27d-89aa-40cb-9974-001b2f927af7
async def test_SecretsClient_set_secret():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"key": "my-key", "status": "created"})

    client = SecretsClient(facade)

    result = await client.set_secret(
        "my-key", "my-value", description="desc", force=True
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/secrets",
        json={
            "key": "my-key",
            "value": "my-value",
            "description": "desc",
            "force": True,
        },
    )
    assert result == {"key": "my-key", "status": "created"}


import pytest


@pytest.mark.asyncio
# ID: f032eeeb-c069-431f-8b3b-08d99c03fe27
async def test_SecretsClient_list_secrets():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"secrets": ["KEY_A", "KEY_B"]})

    client = SecretsClient(facade)

    result = await client.list_secrets()

    assert result == {"secrets": ["KEY_A", "KEY_B"]}
    facade._request.assert_awaited_once_with("GET", "/v1/secrets")


import pytest


@pytest.mark.asyncio
# ID: 278fa963-1f02-4603-8f56-08ffeffd1435
async def test_SecretsClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})

    client = SecretsClient(facade)

    assert await client.list_secrets() == {"ok": True}
    facade._request.assert_awaited_once_with("GET", "/v1/secrets")

    facade._request.reset_mock()

    result = await client.set_secret("mykey", "myvalue", description="desc", force=True)
    assert result == {"ok": True}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/secrets",
        json={
            "key": "mykey",
            "value": "myvalue",
            "description": "desc",
            "force": True,
        },
    )

    facade._request.reset_mock()

    result = await client.get_secret("mykey", show=True)
    assert result == {"ok": True}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/secrets/mykey", params={"show": True}
    )

    facade._request.reset_mock()

    result = await client.delete_secret("mykey")
    assert result == {"ok": True}
    facade._request.assert_awaited_once_with("DELETE", "/v1/secrets/mykey")

    facade._request.reset_mock()

    result = await client.rotate_secret("mykey", "rotated")
    assert result == {"ok": True}
    facade._request.assert_awaited_once_with(
        "PUT", "/v1/secrets/mykey/rotate", json={"new_value": "rotated"}
    )



import pytest


@pytest.mark.asyncio
# ID: 548ba91c-4e3e-45ca-a43e-99d47c417d19
async def test_SecretsClient_rotate_secret():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"key": "my-secret", "rotated": True})

    client = SecretsClient(facade)

    result = await client.rotate_secret("my-secret", "new-value-123")

    facade._request.assert_awaited_once_with(
        "PUT", "/v1/secrets/my-secret/rotate", json={"new_value": "new-value-123"}
    )
    assert result == {"key": "my-secret", "rotated": True}

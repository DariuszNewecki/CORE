from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.integrity_client import IntegrityClient


# ID: c1a12968-d2d5-497d-800d-af13e1ffab2f
async def test_IntegrityClient_verify():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "label": "default"})
    client = IntegrityClient(facade)

    result = await client.verify()

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/integrity/verify",
        json={"label": "default"},
    )
    assert result == {"ok": True, "label": "default"}



import pytest


@pytest.mark.asyncio
# ID: 047245a5-dd55-466b-ae46-0da8642c09c2
async def test_IntegrityClient_baseline() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "fingerprint": "abc123"})

    client = IntegrityClient(facade)
    result = await client.baseline("my-label")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/integrity/baseline",
        json={"label": "my-label"},
    )
    assert result == {"status": "ok", "fingerprint": "abc123"}

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


import pytest


@pytest.mark.asyncio
# ID: 18c8285c-815a-41e1-a07d-dfad406e4af0
async def test_FixClient_fix_modularity():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "result": "done"})

    client = FixClient(facade)

    result = await client.fix_modularity(
        write=True, params={"min_score": 0.5, "limit": 10}
    )

    assert result == {"ok": True, "result": "done"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/fix/modularity",
        json={"write": True, "params": {"min_score": 0.5, "limit": 10}},
    )


import pytest


@pytest.mark.asyncio
# ID: bddf1f95-dbb8-49a4-a20d-5492a8e01e5c
async def test_FixClient_fix_all() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "fixed": 3})
    client = FixClient(facade)

    result = await client.fix_all(write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/fix/all",
        json={"write": True},
    )
    assert result == {"status": "ok", "fixed": 3}

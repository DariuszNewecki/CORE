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


import pytest


@pytest.mark.asyncio
# ID: e8fd2f9f-9f75-4658-bea2-e0e0aca73757
async def test_ProjectClient_promote():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "promoted": True})

    client = ProjectClient(facade)

    result = await client.promote("/some/machinery/path")

    assert result == {"ok": True, "promoted": True}
    facade._request.assert_awaited_once_with(
        "POST", "/v1/project/onboard/promote", json={"path": "/some/machinery/path"}
    )


import asyncio


# ID: 47c9d8b8-1b77-4067-acdb-a27dc9239199
def test_ProjectClient_onboard():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "project_id": "p-123"})

    client = ProjectClient(facade)

    result = asyncio.run(client.onboard("/tmp/repo", write=True, stage=False))

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/project/onboard",
        json={"path": "/tmp/repo", "write": True, "stage": False},
    )
    assert result == {"ok": True, "project_id": "p-123"}


import pytest


@pytest.mark.asyncio
# ID: c7ff4f7f-fe95-4f94-83c8-e2dce84e3f3e
async def test_ProjectClient_generate_docs():
    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={"status": "ok", "path": "docs/10_CAPABILITY_REFERENCE.md"}
    )
    client = ProjectClient(facade)

    result = await client.generate_docs()

    facade._request.assert_awaited_once_with(
        "POST", "/v1/project/docs", json={"output": "docs/10_CAPABILITY_REFERENCE.md"}
    )
    assert result == {"status": "ok", "path": "docs/10_CAPABILITY_REFERENCE.md"}

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.refactor_client import RefactorClient


@pytest.mark.asyncio
# ID: 0fdfed91-30c1-4bb1-a678-ba38ad90bd13
async def test_RefactorClient_poll_refactor_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(
        return_value={"status": "succeeded", "id": "run-123"}
    )

    client = RefactorClient(facade)

    result = await client.poll_refactor_run("run-123", timeout_seconds=42.0)

    assert result == {"status": "succeeded", "id": "run-123"}
    facade._poll_at_path.assert_awaited_once_with(
        "/v1/refactor/runs/run-123", timeout_seconds=42.0
    )


import asyncio


# ID: 2a60d2bd-61ab-4907-a8ba-3d298f491650
def test_RefactorClient_get_refactor_run():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "completed"})
    client = RefactorClient(facade)

    result = asyncio.run(client.get_refactor_run("run-123"))

    facade._request.assert_awaited_once_with("GET", "/v1/refactor/runs/run-123")
    assert result == {"id": "run-123", "status": "completed"}


# ID: 464af4e1-fd9d-4da5-a22e-2209c3ea86b3
async def test_RefactorClient_refactor_autonomous() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "cycle": 42})

    client = RefactorClient(facade)

    result = await client.refactor_autonomous("reduce complexity", write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/refactor/autonomous",
        json={"goal": "reduce complexity", "write": True},
    )
    assert result == {"status": "ok", "cycle": 42}


# ID: 41bf5e2c-05a1-4c5c-8692-3274dc8d754d
def test_RefactorClient_refactor_stats():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"buckets": [1, 2, 3]})
    client = RefactorClient(facade)

    result = asyncio.run(client.refactor_stats())

    assert result == {"buckets": [1, 2, 3]}
    facade._request.assert_awaited_once_with("GET", "/v1/refactor/stats", timeout=300.0)


import pytest


@pytest.mark.asyncio
# ID: 607fc3bd-bffa-4421-9738-78bf9fc42742
async def test_RefactorClient_refactor_candidates():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"candidates": []})

    client = RefactorClient(facade)

    result = await client.refactor_candidates(min_score=0.75, limit=10)

    assert result == {"candidates": []}
    facade._request.assert_awaited_once_with(
        "GET",
        "/v1/refactor/candidates",
        params={"limit": 10, "min_score": 0.75},
        timeout=300.0,
    )


# ID: 06e83689-46fc-42de-ad79-90822dc53162
def test_RefactorClient_refactor_score():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"score": 42})
    client = RefactorClient(facade)

    result = asyncio.run(client.refactor_score("src/module.py"))

    facade._request.assert_awaited_once_with(
        "GET", "/v1/refactor/score", params={"file": "src/module.py"}
    )
    assert result == {"score": 42}



import pytest


@pytest.mark.asyncio
# ID: 2ee60e03-2cc4-48c9-b5a4-d44931ab380b
async def test_RefactorClient_refactor_threshold():
    facade = MagicMock()
    expected = {"threshold": 7, "status": "ok"}
    facade._request = AsyncMock(return_value=expected)

    client = RefactorClient(facade)

    result = await client.refactor_threshold()

    assert result == expected
    facade._request.assert_awaited_once_with("GET", "/v1/refactor/threshold")

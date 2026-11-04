from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.census_client import CensusClient


# ID: 56f51aa3-8a98-421f-aba0-ee9a271e4a67
async def test_CensusClient_census_diff() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"diff": []})

    client = CensusClient(facade)

    result = await client.census_diff(baseline="b123")

    facade._request.assert_awaited_once_with(
        "GET", "/v1/census/diff", params={"baseline": "b123"}
    )
    assert result == {"diff": []}


# ID: 1838f124-704d-471e-bf72-bf959a5d59c3
async def test_CensusClient_census_list_baselines():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"baselines": ["default", "experimental"]})

    client = CensusClient(facade)

    result = await client.census_list_baselines()

    facade._request.assert_awaited_once_with("GET", "/v1/census/baselines")
    assert result == {"baselines": ["default", "experimental"]}


import pytest


@pytest.mark.asyncio
# ID: 54001f2d-f145-4fca-a70d-61d40d8ffd95
async def test_CensusClient_census_create_baseline() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"name": "my-baseline", "id": "b1"})

    client = CensusClient(facade)

    result = await client.census_create_baseline(
        "my-baseline", snapshot_file="snap.json"
    )

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/census/baselines/my-baseline",
        json={"snapshot_file": "snap.json"},
    )
    assert result == {"name": "my-baseline", "id": "b1"}


import asyncio


# ID: d67649aa-a390-4854-96e4-87c74a90348c
def test_CensusClient_poll_census_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(
        return_value={"status": "complete", "run_id": "r1"}
    )

    client = CensusClient(facade)

    result = asyncio.run(client.poll_census_run("r1"))

    facade._poll_at_path.assert_awaited_once_with(
        "/v1/census/runs/r1", timeout_seconds=1800.0
    )
    assert result == {"status": "complete", "run_id": "r1"}




# ID: 32510256-4e40-46a1-907a-e459c2a629c5
async def test_CensusClient_get_census_run():
    facade = AsyncMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "completed"})

    client = CensusClient(facade)

    result = await client.get_census_run("run-123")

    facade._request.assert_awaited_once_with("GET", "/v1/census/runs/run-123")
    assert result == {"id": "run-123", "status": "completed"}

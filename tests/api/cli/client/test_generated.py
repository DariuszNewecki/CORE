from __future__ import annotations

from unittest.mock import patch

from api.cli.client import CoreApiClient


# ID: 6fa8d435-82c0-4248-8f66-18169a9f0700
def test_CoreApiClient():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://127.0.0.1:8000", None)
    ) as mock_parse:
        client = CoreApiClient(base_url="http://127.0.0.1:8000")

    mock_parse.assert_called_once_with("http://127.0.0.1:8000")
    assert client.base_url == "http://127.0.0.1:8000"
    assert client._http_base == "http://127.0.0.1:8000"
    assert client.socket_path is None
    assert client.timeout == 30.0

    # Namespace sub-clients are attached and bound to this client
    assert client.audits is not None
    assert client.fix is not None
    assert client.quality is not None
    assert client.coverage is not None
    assert client.refactor is not None
    assert client.inspect is not None
    assert client.proposals is not None
    assert client.integration is not None
    assert client.census is not None
    assert client.cognitive_roles is not None
    assert client.sync is not None
    assert client.daemon is not None
    assert client.findings is not None
    assert client.integrity is not None
    assert client.lane is not None
    assert client.llm_resources is not None
    assert client.secrets is not None
    assert client.symbols is not None
    assert client.vectors is not None
    assert client.project is not None


from api.cli.client import parse_base_url


# ID: faa64332-60ef-48ab-bf6a-661edaf72f53
def test_parse_base_url():
    assert parse_base_url("http://core:8080") == ("http://core:8080", None)
    assert parse_base_url("unix:///run/core/api/api.sock") == (
        "http://localhost",
        "/run/core/api/api.sock",
    )


from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
# ID: e2b3a937-939c-4a6e-aea8-89c8ed15656a
async def test_CoreApiClient_sync_vectors():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"status": "ok", "synced": 3}
    client.sync = MagicMock()
    client.sync.sync_vectors = AsyncMock(return_value=expected)

    result = await client.sync_vectors("param1", key="value")

    assert result == expected
    client.sync.sync_vectors.assert_awaited_once_with("param1", key="value")


# ID: 0a74de7b-98f5-4437-8adf-cae1373f3aa4
async def test_CoreApiClient_sync_knowledge_graph():
    client = CoreApiClient(base_url="http://localhost:9999")
    client.sync = MagicMock()
    client.sync.sync_knowledge_graph = AsyncMock(return_value={"ok": True})

    result = await client.sync_knowledge_graph("a", key="b")

    client.sync.sync_knowledge_graph.assert_awaited_once_with("a", key="b")
    assert result == {"ok": True}


import pytest


@pytest.mark.asyncio
# ID: 0e450216-f0d5-410c-85a6-6752937c82d1
async def test_core_api_client_census_diff():
    client = CoreApiClient(base_url="http://localhost:8000")
    expected = {"added": [], "removed": [], "changed": []}
    client.census.census_diff = AsyncMock(return_value=expected)

    result = await client.census_diff()

    assert result == expected
    client.census.census_diff.assert_awaited_once_with()


import asyncio


# ID: 6795d260-f9a1-435b-8b9f-0584e7363721
def test_CoreApiClient_census_list_baselines():
    import api.cli.client as client_module

    with patch.object(
        client_module, "parse_base_url", return_value=("http://localhost:8000", None)
    ):
        client = client_module.CoreApiClient(base_url="http://localhost:8000")

        expected = {"baselines": [{"id": "b1", "name": "baseline-one"}]}
        client.census = MagicMock()
        client.census.census_list_baselines = AsyncMock(return_value=expected)

        result = asyncio.run(client.census_list_baselines(limit=10, offset=0))

        assert result == expected
        client.census.census_list_baselines.assert_awaited_once_with(limit=10, offset=0)

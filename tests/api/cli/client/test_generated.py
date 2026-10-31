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


# ID: beb02748-78e8-4273-9fdf-ae9673d5bc4b
async def test_CoreApiClient_quality_imports():
    from api.cli.client import CoreApiClient

    expected = {"imports": ["a", "b"]}

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost")

    client.quality.quality_imports = AsyncMock(return_value=expected)

    result = await client.quality_imports("a", b=2)

    assert result == expected
    client.quality.quality_imports.assert_awaited_once_with("a", b=2)


import pytest


@pytest.mark.asyncio
# ID: 40fb11fc-3160-45af-a6ac-7fd444575f3f
async def test_CoreApiClient_get_fix_run():
    client = CoreApiClient(base_url="http://testserver")

    expected = {"run_id": "abc123", "status": "completed"}
    mock_fix = MagicMock()
    mock_fix.get_fix_run = AsyncMock(return_value=expected)
    client.fix = mock_fix

    result = await client.get_fix_run(run_id="abc123")

    assert result == expected
    mock_fix.get_fix_run.assert_awaited_once_with(run_id="abc123")


import pytest


@pytest.mark.asyncio
# ID: ab7fbacb-e030-4004-a0b4-87a0ac41d856
async def test_CoreApiClient_fix_ir():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.fix = MagicMock()
    client.fix.fix_ir = AsyncMock(return_value={"status": "ok", "fixed": True})

    result = await client.fix_ir(target="symbol_x")

    client.fix.fix_ir.assert_awaited_once_with(target="symbol_x")
    assert result == {"status": "ok", "fixed": True}


# ID: 0fa49ecd-d2b3-40b8-9e0a-8e52a8f9e22f
async def test_CoreApiClient_fix_modularity():
    client = CoreApiClient(base_url="http://localhost:8000")
    expected = {"status": "ok", "result": "modularity_fixed"}

    mock_fix = MagicMock()
    mock_fix.fix_modularity = AsyncMock(return_value=expected)
    client.fix = mock_fix

    result = await client.fix_modularity("arg1", key="value")

    assert result == expected
    mock_fix.fix_modularity.assert_awaited_once_with("arg1", key="value")


# ID: 29828eb3-2092-4ede-9fcd-9b7b15afcf4f
def test_CoreApiClient_get_census_run():
    import asyncio

    from api.cli.client import CoreApiClient

    with (
        patch(
            "api.cli.client.parse_base_url",
            return_value=("http://localhost:8000", None),
        ),
        patch.multiple(
            "api.cli.client",
            AuditClient=MagicMock(),
            FixClient=MagicMock(),
            QualityClient=MagicMock(),
            CoverageClient=MagicMock(),
            RefactorClient=MagicMock(),
            InspectClient=MagicMock(),
            ProposalsClient=MagicMock(),
            IntegrationClient=MagicMock(),
            CensusClient=MagicMock(),
            CognitiveRolesClient=MagicMock(),
            SyncClient=MagicMock(),
            DaemonClient=MagicMock(),
            FindingsClient=MagicMock(),
            IntegrityClient=MagicMock(),
            LaneClient=MagicMock(),
            LlmResourcesClient=MagicMock(),
            SecretsClient=MagicMock(),
            SymbolsClient=MagicMock(),
            VectorsClient=MagicMock(),
            ProjectClient=MagicMock(),
        ),
    ):
        client = CoreApiClient(base_url="http://localhost:8000")
        client.census = MagicMock()
        expected = {"run_id": "abc123", "status": "complete"}
        client.census.get_census_run = AsyncMock(return_value=expected)

        result = asyncio.run(client.get_census_run(run_id="abc123"))

        assert result == expected
        client.census.get_census_run.assert_awaited_once_with(run_id="abc123")


import pytest


@pytest.mark.asyncio
# ID: d7ea6cc5-03cb-4607-8713-d33d9bc3f083
async def test_CoreApiClient_census_run():
    client = CoreApiClient(base_url="http://127.0.0.1:8000")

    expected = {"status": "ok", "run_id": "abc123"}
    census_instance = MagicMock()
    census_instance.census_run = AsyncMock(return_value=expected)
    client.census = census_instance

    result = await client.census_run(path="src", depth=2)

    assert result == expected
    census_instance.census_run.assert_awaited_once_with(path="src", depth=2)


import pytest


@pytest.mark.asyncio
# ID: f6a3ea23-a5dc-4288-abe2-98f9af8f5cf6
async def test_CoreApiClient_inspect_search_commands():
    client = CoreApiClient(base_url="http://localhost:8000")
    expected = {"commands": ["foo", "bar"]}
    client.inspect.inspect_search_commands = AsyncMock(return_value=expected)

    result = await client.inspect_search_commands("query", limit=5)

    assert result == expected
    client.inspect.inspect_search_commands.assert_awaited_once_with("query", limit=5)


# ID: 404c3830-c000-4918-8421-22ad1d9b0e9c
async def test_CoreApiClient_inspect_search_capabilities():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.inspect = MagicMock()
    client.inspect.inspect_search_capabilities = AsyncMock(
        return_value={"capabilities": ["a", "b"]}
    )

    result = await client.inspect_search_capabilities("q", limit=5)

    assert result == {"capabilities": ["a", "b"]}
    client.inspect.inspect_search_capabilities.assert_awaited_once_with("q", limit=5)


import pytest


@pytest.mark.asyncio
# ID: 6d2a4d31-6ca5-4fde-89b2-077f418c53ae
async def test_CoreApiClient_inspect_components() -> None:
    from api.cli.client import CoreApiClient

    patches = [
        patch("api.cli.client.InspectClient"),
        patch("api.cli.client.AuditClient"),
        patch("api.cli.client.FixClient"),
        patch("api.cli.client.QualityClient"),
        patch("api.cli.client.CoverageClient"),
        patch("api.cli.client.RefactorClient"),
        patch("api.cli.client.ProposalsClient"),
        patch("api.cli.client.IntegrationClient"),
        patch("api.cli.client.CensusClient"),
        patch("api.cli.client.CognitiveRolesClient"),
        patch("api.cli.client.SyncClient"),
        patch("api.cli.client.DaemonClient"),
        patch("api.cli.client.FindingsClient"),
        patch("api.cli.client.IntegrityClient"),
        patch("api.cli.client.LaneClient"),
        patch("api.cli.client.LlmResourcesClient"),
        patch("api.cli.client.SecretsClient"),
        patch("api.cli.client.SymbolsClient"),
        patch("api.cli.client.VectorsClient"),
        patch("api.cli.client.ProjectClient"),
        patch("api.cli.client.parse_base_url", return_value=("http://localhost", None)),
    ]

    mocks = [p.start() for p in patches]
    try:
        mock_inspect_cls = mocks[0]
        mock_inspect_instance = MagicMock()
        expected = {"components": [{"name": "foo"}], "count": 1}
        mock_inspect_instance.inspect_components = AsyncMock(return_value=expected)
        mock_inspect_cls.return_value = mock_inspect_instance

        client = CoreApiClient(base_url="http://localhost")

        result = await client.inspect_components("arg1", key="value")

        mock_inspect_instance.inspect_components.assert_awaited_once_with(
            "arg1", key="value"
        )
        assert result == expected
    finally:
        for p in reversed(patches):
            p.stop()


import pytest


# ID: 57b212a2-ef47-4567-bb3c-d56cee647e40
async def test_CoreApiClient_lint():
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        with patch("api.cli.client.IntegrationClient") as mock_integration_cls:
            client = CoreApiClient(base_url="http://localhost:8000")

            mock_integration = MagicMock()
            mock_integration.lint = AsyncMock(return_value={"status": "ok"})
            client.integration = mock_integration

            result = await client.lint(path="src")

    mock_integration.lint.assert_awaited_once_with(path="src")
    assert result == {"status": "ok"}


import pytest


@pytest.mark.asyncio
# ID: 12ff322d-22bd-4c8f-8868-306393fb4ef3
async def test_CoreApiClient_integrate() -> None:
    client = CoreApiClient(base_url="http://localhost:8000")

    expected_result = {"status": "ok", "integrated": True}
    client.integration.integrate = AsyncMock(return_value=expected_result)

    result = await client.integrate("arg1", key="value")

    client.integration.integrate.assert_awaited_once_with("arg1", key="value")
    assert result == expected_result


# ID: f98b7525-44aa-49dc-8637-6cf2786d5091
async def test_CoreApiClient_execute_proposal():
    client = CoreApiClient.__new__(CoreApiClient)
    client.base_url = "http://localhost:8000"
    client.timeout = 30

    expected = {"status": "ok", "proposal_id": "p-123"}
    client.proposals = MagicMock()
    client.proposals.execute_proposal = AsyncMock(return_value=expected)

    result = await client.execute_proposal("p-123", dry_run=False)

    client.proposals.execute_proposal.assert_awaited_once_with("p-123", dry_run=False)
    assert result == expected




# ID: f60e35cc-6efa-4f41-ad2d-8ef7df3f55dd
async def test_CoreApiClient_reject_proposal() -> None:
    from api.cli.client import CoreApiClient

    client = object.__new__(CoreApiClient)

    expected = {"status": "rejected", "id": "prop-123"}
    proposals = MagicMock()
    proposals.reject_proposal = AsyncMock(return_value=expected)
    client.proposals = proposals

    result = await client.reject_proposal("prop-123", reason="not needed")

    assert result == expected
    proposals.reject_proposal.assert_awaited_once_with("prop-123", reason="not needed")

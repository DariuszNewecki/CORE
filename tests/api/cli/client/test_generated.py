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


# ID: f249aeb3-27e9-426a-8fa6-4dc6594a055e
async def test_CoreApiClient_approve_proposal() -> None:
    with patch("api.cli.client.ProposalsClient", MagicMock()):
        client = CoreApiClient(base_url="unix:///tmp/core.sock")

    mock_proposals = client.proposals
    mock_proposals.approve_proposal = AsyncMock(
        return_value={"id": "prop-1", "status": "approved"}
    )

    result = await client.approve_proposal("prop-1")

    assert result == {"id": "prop-1", "status": "approved"}
    mock_proposals.approve_proposal.assert_awaited_once_with("prop-1")


import pytest


@pytest.mark.asyncio
# ID: 674e6f93-f980-4d89-af02-ccaa46f9341e
async def test_CoreApiClient_list_proposals():
    from api.cli.client import CoreApiClient

    mock_proposals = MagicMock()
    mock_proposals.list_proposals = AsyncMock(return_value={"proposals": []})

    with (
        patch("api.cli.client.parse_base_url", return_value=("http://localhost", None)),
        patch("api.cli.client.ProposalsClient", return_value=mock_proposals),
    ):
        client = CoreApiClient(base_url="http://localhost:8080")
        client.proposals = mock_proposals
        result = await client.list_proposals(status="open")

    mock_proposals.list_proposals.assert_awaited_once_with(status="open")
    assert result == {"proposals": []}


import pytest


@pytest.mark.asyncio
# ID: 2f2370f5-8584-46d5-b004-0ab3526cc83a
async def test_CoreApiClient_create_proposal():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.proposals = MagicMock()
    client.proposals.create_proposal = AsyncMock(
        return_value={"id": "prop-123", "status": "created"}
    )

    result = await client.create_proposal(title="My proposal", description="desc")

    client.proposals.create_proposal.assert_awaited_once_with(
        title="My proposal", description="desc"
    )
    assert result == {"id": "prop-123", "status": "created"}


# ID: 479eb767-edf3-4b1b-b299-5f8293e16e65
async def test_CoreApiClient_daemon_stop() -> None:
    base_url = "http://localhost:8000"
    expected = {"status": "stopped"}

    client = MagicMock(spec=CoreApiClient)
    client.daemon = MagicMock()
    client.daemon.daemon_stop = AsyncMock(return_value=expected)

    kwargs = {"force": True}
    bound = CoreApiClient.daemon_stop
    result = await bound(client, **kwargs)

    client.daemon.daemon_stop.assert_awaited_once_with(**kwargs)
    assert result == expected


import pytest


@pytest.mark.asyncio
# ID: 27b6cc20-c834-4bd8-beba-aa464506c044
async def test_CoreApiClient_daemon_start():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.daemon.daemon_start = AsyncMock(return_value={"status": "started"})

    result = await client.daemon_start("arg1", key="value")

    client.daemon.daemon_start.assert_awaited_once_with("arg1", key="value")
    assert result == {"status": "started"}


# ID: 9fad6583-231d-4195-a82c-9c41997d2d16
async def test_CoreApiClient_daemon_status() -> None:
    # Avoid real network/socket setup in __init__ by patching parse_base_url.
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost")

    expected = {"status": "running", "pid": 1234}
    mock_daemon_client = MagicMock()
    mock_daemon_client.daemon_status = AsyncMock(return_value=expected)
    client.daemon = mock_daemon_client

    result = await client.daemon_status(foo="bar")

    assert result == expected
    mock_daemon_client.daemon_status.assert_awaited_once_with(foo="bar")


import pytest


@pytest.mark.asyncio
# ID: 98d1212d-ae98-43a5-961d-8e171d806f5c
async def test_CoreApiClient_verify() -> None:
    expected = {"verified": True, "issues": []}

    with pytest.MonkeyPatch.context() as mp:
        fake_integrity = MagicMock()
        fake_integrity.verify = AsyncMock(return_value=expected)

        client = CoreApiClient.__new__(CoreApiClient)
        client.integrity = fake_integrity

        result = await client.verify(object_id="sym-1", deep=True)

    assert result == expected
    fake_integrity.verify.assert_awaited_once_with(object_id="sym-1", deep=True)


# ID: e224092c-e544-48fa-80de-2f4aeece4eda
def test_CoreApiClient_baseline():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"status": "ok", "baseline_id": "abc123"}
    client.integrity = MagicMock()
    client.integrity.baseline = AsyncMock(return_value=expected)

    result = asyncio.run(client.baseline(foo="bar"))

    assert result == expected
    client.integrity.baseline.assert_awaited_once_with(foo="bar")


import pytest


# ID: 2af385cf-749a-4455-8220-660afd8b57ae
async def test_CoreApiClient_poll_sync_run() -> None:
    client = CoreApiClient.__new__(CoreApiClient)
    client.sync = MagicMock()
    client.sync.poll_sync_run = AsyncMock(
        return_value={"status": "running", "run_id": "abc"}
    )

    result = await CoreApiClient.poll_sync_run(client, "run-123", verbose=True)

    assert result == {"status": "running", "run_id": "abc"}
    client.sync.poll_sync_run.assert_awaited_once_with("run-123", verbose=True)


import pytest


# ID: 2c4faae0-128e-463b-b05e-bf57e0edf642
async def test_core_api_client_get_sync_run() -> None:
    client = CoreApiClient(base_url="http://localhost:1234")
    expected = {"run_id": "run-42", "status": "completed"}
    client.sync = AsyncMock()
    client.sync.get_sync_run = AsyncMock(return_value=expected)

    result = await client.get_sync_run("run-42")

    assert result == expected
    client.sync.get_sync_run.assert_awaited_once_with("run-42")


# ID: 23f562d4-c1cd-4c83-b136-baa61baff01d
async def test_sync_dev_sync() -> None:
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

        expected = {"ok": True, "synced": 3}
        client.sync = MagicMock()
        client.sync.sync_dev_sync = AsyncMock(return_value=expected)

        result = await client.sync_dev_sync("arg1", key="value")

        assert result == expected
        client.sync.sync_dev_sync.assert_awaited_once_with("arg1", key="value")


import pytest


@pytest.mark.asyncio
# ID: 374ad8e7-f02e-4a2b-ae62-fa5c411fe4ba
async def test_CoreApiClient_sync_code_vectors() -> None:
    client = CoreApiClient(base_url="http://example.test")
    expected = {"synced": 3, "vectors": 42}
    client.sync = MagicMock()
    client.sync.sync_code_vectors = AsyncMock(return_value=expected)

    result = await client.sync_code_vectors("payload", key="value")

    assert result == expected
    client.sync.sync_code_vectors.assert_awaited_once_with("payload", key="value")


# ID: c55584d2-14a3-47c6-be2c-c0642e327f97
async def test_CoreApiClient_census_create_baseline() -> None:
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ) as mock_parse:
        client = CoreApiClient(base_url="http://localhost:8000")

    client.census = MagicMock()
    client.census.census_create_baseline = AsyncMock(
        return_value={"name": "baseline-1", "status": "created"}
    )

    result = await client.census_create_baseline("baseline-1", ref="main")

    client.census.census_create_baseline.assert_awaited_once_with(
        "baseline-1", ref="main"
    )
    assert result == {"name": "baseline-1", "status": "created"}


import pytest


@pytest.mark.asyncio
# ID: fd1d56b1-2bd2-4134-a999-ba6eb878b8e6
async def test_CoreApiClient_poll_census_run():
    from api.cli.client import CoreApiClient

    patches = [
        patch("api.cli.client.parse_base_url", return_value=("http://localhost", None)),
        patch("api.cli.client.AuditClient"),
        patch("api.cli.client.FixClient"),
        patch("api.cli.client.QualityClient"),
        patch("api.cli.client.CoverageClient"),
        patch("api.cli.client.RefactorClient"),
        patch("api.cli.client.InspectClient"),
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
    ]

    for p in patches:
        p.start()
    try:
        client = CoreApiClient(base_url="http://localhost:8000")
    finally:
        for p in patches:
            p.stop()

    expected = {"status": "completed", "run_id": "abc"}
    client.census.poll_census_run = AsyncMock(return_value=expected)

    result = await client.poll_census_run("run-123", verbose=True)

    assert result == expected
    client.census.poll_census_run.assert_awaited_once_with("run-123", verbose=True)


import pytest


# ID: b2a8272c-47f1-47f5-85e6-9ac7d96fec75
async def test_CoreApiClient_analysis_test_targets() -> None:
    client = CoreApiClient(base_url="http://localhost:8000")

    mock_inspect = MagicMock()
    mock_inspect.analysis_test_targets = AsyncMock(
        return_value={"targets": ["tests/test_a.py"]}
    )
    client.inspect = mock_inspect

    result = await client.analysis_test_targets(path="src", depth=2)

    mock_inspect.analysis_test_targets.assert_awaited_once_with(path="src", depth=2)
    assert result == {"targets": ["tests/test_a.py"]}


# ID: dcbfe048-6cf4-4ba3-8b58-b5e043ebb7bc
async def test_CoreApiClient_analysis_command_tree() -> None:
    with patch(
        "api.cli.client.parse_base_url",
        return_value=("http://localhost", "/tmp/socket"),
    ):
        client = CoreApiClient(base_url="http://localhost:8080")

    expected = {"tree": ["a", "b"]}
    client.inspect = MagicMock()
    client.inspect.analysis_command_tree = AsyncMock(return_value=expected)

    result = await client.analysis_command_tree("root", depth=2)

    assert result == expected
    client.inspect.analysis_command_tree.assert_awaited_once_with("root", depth=2)


import pytest


# ID: c99c6399-e76e-4570-851f-f04418e7619a
async def test_CoreApiClient_analysis_common_knowledge() -> None:
    expected = {"knowledge": ["a", "b"]}

    mock_inspect = MagicMock()
    mock_inspect.analysis_common_knowledge = AsyncMock(return_value=expected)

    with (
        patch(
            "api.cli.client.parse_base_url",
            return_value=("http://localhost:8080", None),
        ),
        patch("api.cli.client.InspectClient", return_value=mock_inspect),
        patch("api.cli.client.AuditClient", return_value=MagicMock()),
        patch("api.cli.client.FixClient", return_value=MagicMock()),
        patch("api.cli.client.QualityClient", return_value=MagicMock()),
        patch("api.cli.client.CoverageClient", return_value=MagicMock()),
        patch("api.cli.client.RefactorClient", return_value=MagicMock()),
    ):
        client = CoreApiClient(base_url="http://localhost:8080")

    with patch.object(client, "inspect", mock_inspect):
        result = await client.analysis_common_knowledge("arg1", key="value")

    assert result == expected
    mock_inspect.analysis_common_knowledge.assert_awaited_once_with("arg1", key="value")


# ID: 471aa5c8-5e75-47be-a7ee-4ecc3fe55fac
async def test_CoreApiClient_analysis_duplicates():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        for client_attr in (
            "AuditClient",
            "FixClient",
            "QualityClient",
            "CoverageClient",
            "RefactorClient",
            "InspectClient",
            "ProposalsClient",
            "IntegrationClient",
            "CensusClient",
            "CognitiveRolesClient",
            "SyncClient",
            "DaemonClient",
            "FindingsClient",
            "IntegrityClient",
            "LaneClient",
            "LlmResourcesClient",
            "SecretsClient",
            "SymbolsClient",
            "VectorsClient",
            "ProjectClient",
        ):
            with patch(f"api.cli.client.{client_attr}", MagicMock()):
                client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"duplicates": [], "count": 0}
    client.inspect.analysis_duplicates = AsyncMock(return_value=expected)

    result = await client.analysis_duplicates(path="src", min_lines=5)

    assert result == expected
    client.inspect.analysis_duplicates.assert_awaited_once_with(path="src", min_lines=5)


import pytest


@pytest.mark.asyncio
# ID: fa1a08ef-4d1d-4314-b59a-6eb4390c3c6f
async def test_CoreApiClient_analysis_clusters():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.inspect.analysis_clusters = AsyncMock(return_value={"clusters": []})

    result = await client.analysis_clusters(limit=5)

    assert result == {"clusters": []}
    client.inspect.analysis_clusters.assert_awaited_once_with(limit=5)


# ID: 74989f89-03cb-4e84-b0ba-f9d4e73fdf37
async def test_CoreApiClient_refusals_stats():
    fake_inspect = MagicMock()
    fake_clients = [
        "AuditClient",
        "FixClient",
        "QualityClient",
        "CoverageClient",
        "RefactorClient",
        "ProposalsClient",
        "IntegrationClient",
        "CensusClient",
        "CognitiveRolesClient",
        "SyncClient",
        "DaemonClient",
        "FindingsClient",
        "IntegrityClient",
        "LaneClient",
        "LlmResourcesClient",
        "SecretsClient",
        "SymbolsClient",
        "VectorsClient",
        "ProjectClient",
    ]

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", "socket")
    ):
        with patch("api.cli.client.InspectClient", return_value=fake_inspect):
            with patch.multiple(
                "api.cli.client",
                **{name: MagicMock() for name in fake_clients},
            ):
                client = CoreApiClient(base_url="http://localhost:8080")

    expected = {"total": 5, "stats": []}
    fake_inspect.refusals_stats = AsyncMock(return_value=expected)

    result = await client.refusals_stats(limit=10, since="2024-01-01")

    assert result == expected
    fake_inspect.refusals_stats.assert_awaited_once_with(limit=10, since="2024-01-01")


import pytest


@pytest.mark.asyncio
# ID: 53f67299-2765-40ed-b048-fd5cfe641a59
async def test_CoreApiClient_refusals_list():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"refusals": [], "total": 0}
    client.inspect = MagicMock()
    client.inspect.refusals_list = AsyncMock(return_value=expected)

    result = await client.refusals_list(limit=10, offset=0)

    client.inspect.refusals_list.assert_awaited_once_with(limit=10, offset=0)
    assert result == expected


# ID: 5937f00e-2f54-42c1-bb00-462fed1f4090
async def test_CoreApiClient_decisions_patterns() -> None:
    # Arrange: build the client without touching real I/O
    with patch(
        "api.cli.client.parse_base_url",
        return_value=("http://localhost", None),
    ):
        client = CoreApiClient(base_url="http://localhost")

    # Stub the external inspect service dependency
    expected = {"patterns": ["p1", "p2"]}
    client.inspect = MagicMock()
    client.inspect.decisions_patterns = AsyncMock(return_value=expected)

    # Act
    result = await client.decisions_patterns(arg1="value", flag=True)

    # Assert
    assert result == expected
    client.inspect.decisions_patterns.assert_awaited_once_with(arg1="value", flag=True)


import pytest


@pytest.mark.asyncio
# ID: bdc2ff37-4972-45da-9ca3-cd5da6b25e2b
async def test_CoreApiClient_decisions_list():
    expected = {"decisions": [{"id": 1, "title": "test decision"}]}

    with patch("api.cli.client.InspectClient", MagicMock()) as mock_inspect_cls:
        mock_inspect = MagicMock()
        mock_inspect.decisions_list = AsyncMock(return_value=expected)
        mock_inspect_cls.return_value = mock_inspect

        client = CoreApiClient(base_url="http://localhost:8080")
        client.inspect = mock_inspect

        result = await client.decisions_list(limit=10)

    assert result == expected
    mock_inspect.decisions_list.assert_awaited_once_with(limit=10)


# ID: c65e8688-8cc3-4573-b42c-9b2d60b89ae6
def test_CoreApiClient_status_drift():
    with patch("api.cli.client.InspectClient", MagicMock()):
        client = CoreApiClient(base_url="http://localhost:8000")

        expected = {"drift": []}
        client.inspect.status_drift = AsyncMock(return_value=expected)

        result = asyncio.run(client.status_drift(foo="bar"))

        assert result == expected
        client.inspect.status_drift.assert_awaited_once_with(foo="bar")


import pytest


@pytest.mark.asyncio
# ID: 13f5ecd9-dce2-45f3-ae5c-759603a62e9b
async def test_CoreApiClient_status_db():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.inspect.status_db = AsyncMock(return_value={"status": "ok"})

    result = await client.status_db(foo="bar")

    client.inspect.status_db.assert_awaited_once_with(foo="bar")
    assert result == {"status": "ok"}


import pytest


@pytest.mark.asyncio
# ID: e24df017-a3a7-43e9-851a-fea336822345
async def test_CoreApiClient_poll_refactor_run():
    client = CoreApiClient.__new__(CoreApiClient)
    expected = {"status": "completed", "run_id": "abc"}
    mock_refactor = MagicMock()
    mock_refactor.poll_refactor_run = AsyncMock(return_value=expected)
    client.refactor = mock_refactor

    result = await client.poll_refactor_run(run_id="abc")

    assert result == expected
    mock_refactor.poll_refactor_run.assert_awaited_once_with(run_id="abc")


# ID: f7613c18-83a5-445a-9e5c-b74ddb41df0c
def test_CoreApiClient_get_refactor_run():
    from api.cli.client import CoreApiClient

    with patch.multiple(
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
        parse_base_url=MagicMock(return_value=("http://localhost", None)),
    ):
        client = CoreApiClient(base_url="http://localhost")

    expected = {"run_id": "run-123", "status": "completed"}
    client.refactor = MagicMock()
    client.refactor.get_refactor_run = AsyncMock(return_value=expected)

    result = asyncio.run(client.get_refactor_run(run_id="run-123"))

    assert result == expected
    client.refactor.get_refactor_run.assert_awaited_once_with(run_id="run-123")


import pytest


# ID: 6ad09fa5-b1dc-4261-bcae-9811a2d45f4f
async def test_CoreApiClient_refactor_autonomous():
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ):
        obj = CoreApiClient(base_url="http://localhost:8000")

    fake_result = {"status": "ok", "refactors": []}
    obj.refactor = MagicMock()
    obj.refactor.refactor_autonomous = AsyncMock(return_value=fake_result)

    result = await obj.refactor_autonomous("repo", dry_run=True)

    obj.refactor.refactor_autonomous.assert_awaited_once_with("repo", dry_run=True)
    assert result == fake_result


import pytest


@pytest.mark.asyncio
# ID: daa42747-b281-4937-a639-50ea7336ca95
async def test_CoreApiClient_refactor_stats():
    client = CoreApiClient.__new__(CoreApiClient)
    client.refactor = MagicMock()
    client.refactor.refactor_stats = AsyncMock(
        return_value={"total": 42, "by_kind": {}}
    )

    result = await CoreApiClient.refactor_stats(client, "some-arg", key="value")

    assert result == {"total": 42, "by_kind": {}}
    client.refactor.refactor_stats.assert_awaited_once_with("some-arg", key="value")


# ID: 917f67a3-5c94-4b33-bc51-e1ea198100d5
async def test_CoreApiClient_refactor_candidates() -> None:
    with (
        patch(
            "api.cli.client.parse_base_url",
            return_value=("http://localhost:8000", None),
        ),
        patch("api.cli.client.RefactorClient") as mock_refactor_cls,
    ):
        mock_refactor = MagicMock()
        mock_refactor.refactor_candidates = AsyncMock(return_value={"candidates": []})
        mock_refactor_cls.return_value = mock_refactor

        client = CoreApiClient(base_url="http://localhost:8000")

        result = await client.refactor_candidates(limit=5)

        assert result == {"candidates": []}
        mock_refactor.refactor_candidates.assert_awaited_once_with(limit=5)


import pytest


@pytest.mark.asyncio
# ID: a5d86c74-ee04-4878-9c22-db4476916edb
async def test_CoreApiClient_refactor_score():
    from api.cli.client import CoreApiClient

    expected_result = {"score": 0.87, "grade": "A"}

    with patch("api.cli.client.RefactorClient") as mock_refactor_cls:
        mock_refactor_instance = MagicMock()
        mock_refactor_instance.refactor_score = AsyncMock(return_value=expected_result)
        mock_refactor_cls.return_value = mock_refactor_instance

        with patch(
            "api.cli.client.parse_base_url", return_value=("http://localhost", None)
        ):
            client = CoreApiClient(base_url="http://localhost:8000")

        result = await client.refactor_score(path="src/foo.py", depth=2)

    assert result == expected_result
    mock_refactor_instance.refactor_score.assert_awaited_once_with(
        path="src/foo.py", depth=2
    )


import pytest


@pytest.mark.asyncio
# ID: c984eb1b-52d1-404d-84fd-17e6c733b685
async def test_CoreApiClient_refactor_threshold():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        with patch("api.cli.client.RefactorClient") as mock_refactor_cls:
            mock_refactor_instance = MagicMock()
            mock_refactor_instance.refactor_threshold = AsyncMock(
                return_value={"threshold": 0.75}
            )
            mock_refactor_cls.return_value = mock_refactor_instance

            client = CoreApiClient(base_url="http://localhost")
            client.refactor = mock_refactor_instance

            result = await client.refactor_threshold(foo="bar")

            assert result == {"threshold": 0.75}
            mock_refactor_instance.refactor_threshold.assert_awaited_once_with(
                foo="bar"
            )


import pytest


@pytest.mark.asyncio
# ID: 544cbfb6-1fe5-456f-b9ea-35928534cde4
async def test_CoreApiClient_tests_interactive():
    client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"ok": True, "result": "interactive"}

    mock_coverage = MagicMock()
    mock_coverage.tests_interactive = AsyncMock(return_value=expected)
    client.coverage = mock_coverage

    result = await client.tests_interactive("arg1", key="value")

    assert result == expected
    mock_coverage.tests_interactive.assert_awaited_once_with("arg1", key="value")


# ID: 4a293f15-e832-4f7e-aabc-b555ed9176ee
async def test_CoreApiClient_poll_coverage_run() -> None:
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    client.coverage = MagicMock()
    client.coverage.poll_coverage_run = AsyncMock(return_value={"status": "ok"})

    result = await client.poll_coverage_run("run-123", timeout=5)

    client.coverage.poll_coverage_run.assert_awaited_once_with("run-123", timeout=5)
    assert result == {"status": "ok"}


import pytest


# ID: 8b789045-ec4d-43f1-a14e-e63a1c703a91
async def test_CoreApiClient_get_coverage_run() -> None:
    client_mocks = [
        "AuditClient",
        "FixClient",
        "QualityClient",
        "CoverageClient",
        "RefactorClient",
        "InspectClient",
        "ProposalsClient",
        "IntegrationClient",
        "CensusClient",
        "CognitiveRolesClient",
        "SyncClient",
        "DaemonClient",
        "FindingsClient",
        "IntegrityClient",
        "LaneClient",
        "LlmResourcesClient",
        "SecretsClient",
        "SymbolsClient",
        "VectorsClient",
        "ProjectClient",
    ]

    patchers = [patch("api.cli.client." + name, MagicMock()) for name in client_mocks]
    patchers.append(
        patch("api.cli.client.parse_base_url", return_value=("http://localhost", None))
    )

    active = [p.start() for p in patchers]
    try:
        from api.cli.client import CoreApiClient

        client = CoreApiClient(base_url="http://localhost:8000")

        expected = {"run_id": "abc123", "coverage": 0.87}
        client.coverage.get_coverage_run = AsyncMock(return_value=expected)

        result = await client.get_coverage_run(run_id="abc123")

        assert result == expected
        client.coverage.get_coverage_run.assert_awaited_once_with(run_id="abc123")
    finally:
        for p in patchers:
            p.stop()


import pytest


@pytest.mark.asyncio
# ID: cd32e23b-7753-4252-84fe-e0f670b3e28a
async def test_CoreApiClient_coverage_generate_batch():
    # Instantiate the client under test with an explicit base_url to avoid env/IO.
    client = CoreApiClient(base_url="http://localhost:8080")

    # Replace the coverage sub-client with a mock whose async method returns a sentinel.
    expected = {"generated": 3, "status": "ok"}
    mock_coverage = MagicMock()
    mock_coverage.coverage_generate_batch = AsyncMock(return_value=expected)
    client.coverage = mock_coverage

    result = await client.coverage_generate_batch(
        project="my-proj", paths=["a.py", "b.py"]
    )

    mock_coverage.coverage_generate_batch.assert_awaited_once_with(
        project="my-proj", paths=["a.py", "b.py"]
    )
    assert result == expected


# ID: f8e83b71-8daa-4d0d-927f-fc65f8edcf4a
async def test_CoreApiClient_coverage_generate():
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8080")

        mock_coverage = MagicMock()
        mock_coverage.coverage_generate = AsyncMock(return_value={"generated": True})
        client.coverage = mock_coverage

        result = await client.coverage_generate("/some/path", flag=True)

        assert result == {"generated": True}
        mock_coverage.coverage_generate.assert_awaited_once_with(
            "/some/path", flag=True
        )


import pytest


@pytest.mark.asyncio
# ID: d1b7e916-483c-45f7-8a5d-20d8ee9909d4
async def test_CoreApiClient_coverage_methods():
    client = CoreApiClient(base_url="http://localhost:8000")
    client.coverage.coverage_methods = AsyncMock(
        return_value={"methods": [{"name": "foo", "covered": True}]}
    )

    result = await client.coverage_methods("pkg", limit=5)

    client.coverage.coverage_methods.assert_awaited_once_with("pkg", limit=5)
    assert result == {"methods": [{"name": "foo", "covered": True}]}


import pytest


@pytest.mark.asyncio
# ID: 4cb27a01-efa3-420a-9910-d2b949be0f8f
async def test_CoreApiClient_quality_policy_coverage():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")
        expected = {"coverage": 0.85, "policies": []}
        mock_quality = MagicMock()
        mock_quality.quality_policy_coverage = AsyncMock(return_value=expected)
        client.quality = mock_quality

        result = await client.quality_policy_coverage(foo="bar")

        assert result == expected
        mock_quality.quality_policy_coverage.assert_awaited_once_with(foo="bar")


import pytest


@pytest.mark.asyncio
# ID: a1868f8d-cb92-468d-b99f-6a8d344c8a68
async def test_CoreApiClient_coverage_history() -> None:
    client = CoreApiClient(base_url="http://example.test")
    expected = {"status": "ok", "history": []}
    mock_coverage = MagicMock()
    mock_coverage.coverage_history = AsyncMock(return_value=expected)
    client.coverage = mock_coverage

    result = await client.coverage_history(limit=10, since="2024-01-01")

    assert result == expected
    mock_coverage.coverage_history.assert_awaited_once_with(
        limit=10, since="2024-01-01"
    )


# ID: a5273d46-4eb5-4936-9327-bb459098e119
async def test_CoreApiClient_coverage_gaps():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"gaps": [{"file": "a.py", "line": 10}]}

    client.coverage = MagicMock()
    client.coverage.coverage_gaps = AsyncMock(return_value=expected)

    result = await client.coverage_gaps(project="proj", limit=5)

    assert result == expected
    client.coverage.coverage_gaps.assert_awaited_once_with(project="proj", limit=5)


# ID: 83eb237d-366d-46c6-a24c-3586d8289712
def test_CoreApiClient_coverage_targets():
    client = CoreApiClient.__new__(CoreApiClient)

    expected = {"targets": []}
    mock_coverage = MagicMock()
    mock_coverage.coverage_targets = AsyncMock(return_value=expected)
    client.coverage = mock_coverage

    result = asyncio.run(CoreApiClient.coverage_targets(client))

    assert result == expected
    mock_coverage.coverage_targets.assert_awaited_once_with()


import pytest


@pytest.mark.asyncio
# ID: ca01434a-557c-4041-9af5-72b8d7a348b9
async def test_CoreApiClient_coverage_report():
    from api.cli.client import CoreApiClient

    client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"report": "ok"}
    client.coverage = MagicMock()
    client.coverage.coverage_report = AsyncMock(return_value=expected)

    result = await client.coverage_report("arg1", key="value")

    client.coverage.coverage_report.assert_awaited_once_with("arg1", key="value")
    assert result == expected


import pytest


@pytest.mark.asyncio
# ID: e38e279b-235d-4d05-b2eb-e5326a8ce7b3
async def test_CoreApiClient_coverage_check():
    client = CoreApiClient(base_url="http://localhost")

    expected = {"coverage": 0.95}
    mock_instance = object.__new__(type(client.coverage))
    mock_instance.coverage_check = AsyncMock(return_value=expected)
    client.coverage = mock_instance

    result = await client.coverage_check("argv", key="value")

    assert result == expected
    mock_instance.coverage_check.assert_awaited_once_with("argv", key="value")


# ID: 4fb81155-55fe-4bec-bfc9-2131a6412afd
async def test_CoreApiClient_quality_gates():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost:8000", None)
    ):
        client = CoreApiClient(base_url="http://localhost:8000")

    expected = {"gates": [{"name": "gate1", "passed": True}]}
    client.quality = MagicMock()
    client.quality.quality_gates = AsyncMock(return_value=expected)

    result = await client.quality_gates("arg1", key="value")

    client.quality.quality_gates.assert_awaited_once_with("arg1", key="value")
    assert result == expected


# ID: d780c8ce-a0c2-4e88-991d-155c442eb41f
async def test_CoreApiClient_quality_system():
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url",
        return_value=("http://localhost:0", "/tmp/q.sock"),
    ):
        client = CoreApiClient(base_url="http://localhost:0")

    expected = {"ok": True, "payload": {"status": "healthy"}}
    client.quality = MagicMock()
    client.quality.quality_system = AsyncMock(return_value=expected)

    result = await client.quality_system("arg1", key="value")

    assert result == expected
    client.quality.quality_system.assert_awaited_once_with("arg1", key="value")


# ID: 4d027340-eca4-4a6c-96ed-cb1830ef1c12
async def test_CoreApiClient_quality_tests():
    expected = {"status": "ok"}
    quality_mock = MagicMock()
    quality_mock.quality_tests = AsyncMock(return_value=expected)
    with patch.object(CoreApiClient, "__init__", lambda self: None):
        client = CoreApiClient.__new__(CoreApiClient)
    client.quality = quality_mock

    result = await client.quality_tests("arg1", key="value")

    assert result == expected
    quality_mock.quality_tests.assert_awaited_once_with("arg1", key="value")




# ID: d20958ab-b139-4e90-a1f8-4f78d19622ff
def test_CoreApiClient_quality_lint():
    from api.cli.client import CoreApiClient

    with patch(
        "api.cli.client.parse_base_url", return_value=("http://localhost", None)
    ):
        client = CoreApiClient(base_url="http://localhost")

    client.quality = MagicMock()
    client.quality.quality_lint = AsyncMock(return_value={"ok": True})

    import asyncio

    result = asyncio.run(client.quality_lint("arg1", key="value"))

    client.quality.quality_lint.assert_awaited_once_with("arg1", key="value")
    assert result == {"ok": True}

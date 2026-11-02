from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.coverage_client import CoverageClient


@pytest.mark.asyncio
# ID: 4e5c651b-1efa-4af6-a540-9803b23cd184
async def test_CoverageClient() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})
    facade._poll_at_path = AsyncMock(return_value={"status": "completed"})

    client = CoverageClient(facade)

    # Constructor wiring
    assert client._facade is facade

    # Happy-path smoke test of representative methods
    result = await client.coverage_check()
    facade._request.assert_awaited_once_with("GET", "/v1/coverage/check", timeout=300.0)
    assert result == {"ok": True}

    await client.coverage_report(show_missing=True, output_format="html")
    facade._request.assert_awaited_with(
        "GET",
        "/v1/coverage/report",
        params={"show_missing": True, "format": "html"},
        timeout=300.0,
    )

    await client.coverage_generate(target_file="foo.py", write=True)
    facade._request.assert_awaited_with(
        "POST",
        "/v1/coverage/generate",
        json={"target_file": "foo.py", "write": True},
    )

    await client.get_coverage_run("run-123")
    facade._request.assert_awaited_with("GET", "/v1/coverage/runs/run-123")

    poll_result = await client.poll_coverage_run("run-123", timeout_seconds=42.0)
    facade._poll_at_path.assert_awaited_once_with(
        "/v1/coverage/runs/run-123", timeout_seconds=42.0
    )
    assert poll_result == {"status": "completed"}


import pytest


@pytest.mark.asyncio
# ID: 362c4e1b-2e4c-424c-b9b3-1bc1e2e83252
async def test_CoverageClient_tests_interactive():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "tests": []})

    client = CoverageClient(facade)

    result = await client.tests_interactive(target_file="src/foo.py")

    assert result == {"status": "ok", "tests": []}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/tests/interactive",
        json={"target_file": "src/foo.py"},
        timeout=600.0,
    )


# ID: f52dd100-1940-4d0d-9094-0eea12d2a2db
async def test_CoverageClient_poll_coverage_run():
    facade = MagicMock()
    facade._poll_at_path = AsyncMock(
        return_value={"status": "complete", "run_id": "run-123"}
    )

    client = CoverageClient(facade)

    result = await client.poll_coverage_run("run-123", timeout_seconds=42.0)

    facade._poll_at_path.assert_awaited_once_with(
        "/v1/coverage/runs/run-123", timeout_seconds=42.0
    )
    assert result == {"status": "complete", "run_id": "run-123"}


import pytest


@pytest.mark.asyncio
# ID: 226f4398-ba2c-4238-a536-5869dd4a0712
async def test_CoverageClient_get_coverage_run():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"id": "run-123", "status": "complete"})

    client = CoverageClient(facade)

    result = await client.get_coverage_run("run-123")

    facade._request.assert_awaited_once_with("GET", "/v1/coverage/runs/run-123")
    assert result == {"id": "run-123", "status": "complete"}


import asyncio


# ID: e22df961-8bea-4dbb-9a47-d98417e54814
def test_CoverageClient_coverage_generate_batch() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "generated": 3})

    client = CoverageClient(facade)

    result = asyncio.run(client.coverage_generate_batch(priority="high", write=True))

    assert result == {"status": "ok", "generated": 3}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/coverage/generate:batch",
        json={"priority": "high", "write": True},
    )


import pytest


@pytest.mark.asyncio
# ID: ad24c475-c93e-4bec-8e4e-5f5f17afd98a
async def test_CoverageClient_coverage_generate():
    facade = MagicMock()
    facade._request = AsyncMock(
        return_value={"generated": True, "target_file": "foo.py"}
    )

    client = CoverageClient(facade)

    result = await client.coverage_generate("foo.py", write=True)

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/coverage/generate",
        json={"target_file": "foo.py", "write": True},
    )
    assert result == {"generated": True, "target_file": "foo.py"}



import pytest


@pytest.mark.asyncio
# ID: 3807725d-e14f-47de-abce-565ab8422d3d
async def test_CoverageClient_coverage_methods():
    facade = MagicMock()
    expected = {"methods": [{"name": "line"}, {"name": "branch"}]}
    facade._request = AsyncMock(return_value=expected)

    client = CoverageClient(facade)

    result = await client.coverage_methods()

    assert result == expected
    facade._request.assert_awaited_once_with("GET", "/v1/coverage/methods")

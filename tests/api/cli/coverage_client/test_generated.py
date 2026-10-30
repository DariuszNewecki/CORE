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

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.quality_client import QualityClient


@pytest.mark.asyncio
# ID: 8dc2b18c-e43f-47f9-b319-d159e8d088a6
async def test_QualityClient_quality_tests():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "tests": []})
    client = QualityClient(facade)

    result = await client.quality_tests(path="tests/unit")

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/quality/tests",
        json={"path": "tests/unit"},
    )
    assert result == {"status": "ok", "tests": []}


import asyncio


# ID: dce2dfe1-2791-4c24-8f37-6c9236a1feb2
def test_QualityClient_quality_lint():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "issues": []})

    client = QualityClient(facade)

    result = asyncio.run(client.quality_lint(fix=True))

    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/quality/lint",
        json={"fix": True},
    )
    assert result == {"status": "ok", "issues": []}


import pytest


@pytest.mark.asyncio
# ID: 889569d9-2a6d-4f72-9797-08ca78922829
async def test_QualityClient_quality_policy_coverage():
    facade = MagicMock()
    expected = {
        "report_id": "abc123",
        "generated_at_utc": "2024-01-01T00:00:00Z",
        "repo_root": "/repo",
        "summary": {"covered": 5, "total": 5},
        "records": [],
        "exit_code": 0,
    }
    facade._request = AsyncMock(return_value=expected)

    client = QualityClient(facade)

    result = await client.quality_policy_coverage()

    assert result == expected
    facade._request.assert_awaited_once_with(
        "POST", "/v1/quality/policy-coverage", json={}
    )


import pytest


# ID: 6f6f8643-ba76-4e5f-823f-61b34bd83b6b
async def test_QualityClient_quality_imports():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True, "imports": []})

    client = QualityClient(facade)

    result = await client.quality_imports()

    assert result == {"ok": True, "imports": []}
    facade._request.assert_awaited_once_with("POST", "/v1/quality/imports")



import pytest


@pytest.mark.asyncio
# ID: aba874a2-ecde-4ec6-b6bf-179a9deef618
async def test_QualityClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"ok": True})

    client = QualityClient(facade)

    result = await client.quality_imports()
    assert result == {"ok": True}
    facade._request.assert_awaited_once_with("POST", "/v1/quality/imports")

    result = await client.quality_lint(fix=True)
    assert result == {"ok": True}
    facade._request.assert_awaited_with("POST", "/v1/quality/lint", json={"fix": True})

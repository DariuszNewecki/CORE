from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.quality_routes import quality_gates


# ID: 56345ea1-0e64-421c-85c5-65b79bedb33f
async def test_quality_gates():
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_background_tasks = MagicMock()
    mock_payload = MagicMock()
    mock_session = AsyncMock()
    mock_dispatch_response = {"status": "dispatched", "checks": "gates"}

    with patch(
        "api.v1.quality_routes._dispatch_quality",
        new_callable=AsyncMock,
        return_value=mock_dispatch_response,
    ) as mock_dispatch:
        result = await quality_gates(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
            payload=mock_payload,
            session=mock_session,
        )

    assert result == mock_dispatch_response
    mock_dispatch.assert_awaited_once_with(
        check="gates",
        params={},
        requested_by=mock_payload.requested_by,
        request=mock_request,
        response=mock_response,
        background_tasks=mock_background_tasks,
        session=mock_session,
    )


from fastapi import BackgroundTasks


# ID: 5a5487a9-afd7-439c-9e07-4f107c410fcb
async def test_quality_system():
    from api.v1.quality_routes import quality_system

    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock(spec=BackgroundTasks)
    payload = MagicMock()
    payload.requested_by = "tester"
    session = AsyncMock()

    sentinel = {"status": "dispatched", "check": "system"}

    with patch(
        "api.v1.quality_routes._dispatch_quality",
        new=AsyncMock(return_value=sentinel),
    ) as mock_dispatch:
        result = await quality_system(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert result == sentinel
    mock_dispatch.assert_awaited_once_with(
        check="system",
        params={},
        requested_by="tester",
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


import pytest

from api.v1.quality_routes import quality_tests


@pytest.mark.asyncio
# ID: 623fcc92-b220-4e8f-8f0b-67dc8bbc36ad
async def test_quality_tests():
    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock()
    session = MagicMock()
    payload = MagicMock()
    payload.path = "tests/unit"
    payload.requested_by = "user@example.com"

    expected = {"status": "dispatched", "check": "tests"}

    with patch(
        "api.v1.quality_routes._dispatch_quality",
        new=AsyncMock(return_value=expected),
    ) as mock_dispatch:
        result = await quality_tests(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert result == expected
    mock_dispatch.assert_awaited_once_with(
        check="tests",
        params={"path": "tests/unit"},
        requested_by="user@example.com",
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


# ID: da1efe4b-dd90-40fa-ae0b-89ffde74eec6
async def test_quality_lint():
    from api.v1.quality_routes import quality_lint

    request = MagicMock()
    response = MagicMock()
    background_tasks = MagicMock()
    payload = MagicMock()
    payload.fix = True
    payload.requested_by = "tester"
    session = AsyncMock()

    expected = {"status": "ok"}

    with patch(
        "api.v1.quality_routes._dispatch_quality",
        new=AsyncMock(return_value=expected),
    ) as mock_dispatch:
        result = await quality_lint(
            request=request,
            response=response,
            background_tasks=background_tasks,
            payload=payload,
            session=session,
        )

    assert result == expected
    mock_dispatch.assert_awaited_once_with(
        check="lint",
        params={"fix": True},
        requested_by="tester",
        request=request,
        response=response,
        background_tasks=background_tasks,
        session=session,
    )


import asyncio

from api.v1.quality_routes import quality_policy_coverage


# ID: 93b635d8-4ffb-4773-b3fb-180faedb949f
def test_quality_policy_coverage():
    from api.v1 import quality_routes

    expected = {
        "report_id": "rpt-1",
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "repo_root": "/repo",
        "summary": {},
        "records": [],
        "exit_code": 0,
    }

    core_context = MagicMock()
    request = MagicMock()
    request.app.state.core_context = core_context

    original = quality_routes.run_quality_policy_coverage
    quality_routes.run_quality_policy_coverage = AsyncMock(return_value=expected)
    try:
        result = asyncio.run(quality_policy_coverage(request))
    finally:
        quality_routes.run_quality_policy_coverage = original

    assert result == expected


import pytest

from api.v1.quality_routes import quality_imports


@pytest.mark.asyncio
# ID: 8533c0c9-2612-46ad-ae23-5149bb28f3aa
async def test_quality_imports() -> None:
    fake_core_context = MagicMock(name="core_context")

    request = MagicMock()
    request.app.state.core_context = fake_core_context

    expected = {"status": "ok", "violations": []}

    with patch(
        "api.v1.quality_routes.run_quality_imports",
        new=AsyncMock(return_value=expected),
    ) as mock_run:
        result = await quality_imports(request)

    mock_run.assert_awaited_once_with(fake_core_context)
    assert result == expected


from api.v1.quality_routes import QualityAsyncRequest


# ID: 7e74f1ef-c9fe-4376-a910-f1aded8b5b48
def test_QualityAsyncRequest():
    request = QualityAsyncRequest()
    assert request.requested_by == "api"

    custom = QualityAsyncRequest(requested_by="tester")
    assert custom.requested_by == "tester"

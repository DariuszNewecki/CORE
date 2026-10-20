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

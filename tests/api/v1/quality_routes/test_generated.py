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

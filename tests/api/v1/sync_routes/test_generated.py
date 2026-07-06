from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.sync_routes import sync_dev_sync


@pytest.mark.asyncio
# ID: a5b958a7-995d-48c3-b536-bed468e1166f
async def test_sync_dev_sync():
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_background_tasks = MagicMock()
    mock_payload = MagicMock()
    mock_session = MagicMock()
    expected_result = {"status": "queued", "sync_type": "dev_sync"}

    with patch(
        "api.v1.sync_routes._dispatch_sync",
        new_callable=AsyncMock,
        return_value=expected_result,
    ) as mock_dispatch:
        result = await sync_dev_sync(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
            payload=mock_payload,
            session=mock_session,
        )

    assert result == expected_result
    mock_dispatch.assert_awaited_once_with(
        sync_type="dev_sync",
        request=mock_request,
        response=mock_response,
        background_tasks=mock_background_tasks,
        payload=mock_payload,
        session=mock_session,
    )

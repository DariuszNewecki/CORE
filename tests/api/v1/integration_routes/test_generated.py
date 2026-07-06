from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from api.v1.integration_routes import integrate


@pytest.mark.asyncio
# ID: f25f6674-2d2e-4ccb-a2a2-f543add1b8cd
async def test_integrate():
    mock_payload = MagicMock()
    mock_payload.commit_message = "test commit"

    mock_request = AsyncMock(spec=Request)
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    with patch(
        "api.v1.integration_routes.run_integration", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = {"ok": True, "data": "result"}
        result = await integrate(mock_payload, mock_request)

    assert result == {"ok": True, "data": "result"}
    mock_run.assert_awaited_once_with(mock_core_context, "test commit")

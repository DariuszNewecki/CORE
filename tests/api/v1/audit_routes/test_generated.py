from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.audit_routes import create_remediation_run


@pytest.mark.asyncio
# ID: 972d5b25-d748-4565-9e67-0aa7fcc03de4
async def test_create_remediation_run():
    # Arrange
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.core_context = MagicMock()

    mock_response = MagicMock(spec=Response)
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    mock_payload = MagicMock()
    mock_payload.mode = "auto"
    mock_payload.audit_run_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_payload.write = True
    mock_payload.requested_by = "test_user"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = "550e8400-e29b-41d4-a716-446655440001"
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()

    with patch("api.v1.audit_routes.MODE_ALIASES", {"auto": "auto_mode"}):
        # Act
        result = await create_remediation_run(
            request=mock_request,
            response=mock_response,
            background_tasks=mock_background_tasks,
            payload=mock_payload,
            session=mock_session,
        )

    # Assert
    assert result["run_id"] == "550e8400-e29b-41d4-a716-446655440001"
    assert result["status"] == "pending"
    assert result["href"] == f"/v1/audit/remediations/{result['run_id']}"

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
    mock_background_tasks.add_task.assert_called_once()

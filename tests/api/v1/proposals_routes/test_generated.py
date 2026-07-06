from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from api.v1.proposals_routes import API_CLAIMER_UUID, execute_proposal


@pytest.mark.asyncio
# ID: 0daa8800-85d8-46c1-8fd2-c521ab08ec72
async def test_execute_proposal():
    # Arrange
    proposal_id = "proposal-123"
    payload = MagicMock()
    payload.write = True

    request = MagicMock(spec=Request)
    request.app.state.core_context = MagicMock()

    mock_executor = AsyncMock()
    mock_executor.execute.return_value = {
        "status": "executed",
        "proposal_id": proposal_id,
    }

    with patch("api.v1.proposals_routes.ProposalExecutor", return_value=mock_executor):
        # Act
        result = await execute_proposal(proposal_id, payload, request)

    # Assert
    assert result == {"status": "executed", "proposal_id": proposal_id}
    mock_executor.execute.assert_awaited_once_with(
        proposal_id, API_CLAIMER_UUID, write=payload.write
    )

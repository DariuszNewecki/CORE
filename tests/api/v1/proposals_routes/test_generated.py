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

    # #771: execute logic moved to will.governance.proposal_runner, which
    # imports ProposalExecutor from its source module — patch there.
    with patch(
        "will.autonomy.proposal_executor.ProposalExecutor",
        return_value=mock_executor,
    ):
        # Act
        result = await execute_proposal(proposal_id, payload, request)

    # Assert
    assert result == {"status": "executed", "proposal_id": proposal_id}
    mock_executor.execute.assert_awaited_once_with(
        proposal_id, API_CLAIMER_UUID, write=payload.write
    )



import pytest


@pytest.mark.asyncio
# ID: 57f02c11-752f-41a1-9a4a-6ced4d7e1b26
async def test_reject_proposal():
    from api.v1.proposals_routes import reject_proposal

    payload = MagicMock()
    payload.reason = "not a good fit"

    mock_service = MagicMock()
    mock_service.reject = AsyncMock(return_value=3)

    mock_session = MagicMock()

    with patch(
        "api.v1.proposals_routes.ProposalService", return_value=mock_service
    ) as mock_service_cls:
        result = await reject_proposal(
            proposal_id="prop-123",
            payload=payload,
            session=mock_session,
        )

    mock_service_cls.assert_called_once_with(mock_session)
    mock_service.reject.assert_awaited_once_with("prop-123", reason="not a good fit")

    assert result["ok"] is True
    assert result["proposal_id"] == "prop-123"
    assert result["reason"] == "not a good fit"
    assert result["revived_count"] == 3
    assert result["status"] == "rejected"

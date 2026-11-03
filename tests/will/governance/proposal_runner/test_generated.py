from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from will.governance.proposal_runner import execute_proposal_direct


@pytest.mark.asyncio
# ID: 1a879f60-ca9b-4d73-9c21-55c8e5e383cb
async def test_execute_proposal_direct():
    context = MagicMock()
    proposal_id = "prop-123"
    claimer = uuid4()
    expected_result = {"status": "executed", "proposal_id": proposal_id}

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=expected_result)

    with patch(
        "will.autonomy.proposal_executor.ProposalExecutor",
        return_value=mock_executor,
    ) as mock_executor_cls:
        result = await execute_proposal_direct(
            context,
            proposal_id=proposal_id,
            claimer=claimer,
            write=True,
        )

    mock_executor_cls.assert_called_once_with(context)
    mock_executor.execute.assert_awaited_once_with(proposal_id, claimer, write=True)
    assert result == expected_result

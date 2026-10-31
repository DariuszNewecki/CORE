from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_state_manager import ProposalStateManager


# ID: 3b2b81b9-728c-4a42-901a-403b934b5907
async def test_ProposalStateManager_reject():
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    manager = ProposalStateManager(session)

    with patch("will.autonomy.proposal_state_manager.logger") as mock_logger:
        await manager.reject("prop-123", "not viable")

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    mock_logger.info.assert_called_once_with(
        "Rejected proposal: %s - %s", "prop-123", "not viable"
    )


# ID: c2c974b6-cf98-46a9-98e5-26070ca9bb56
async def test_ProposalStateManager_approve():
    session = MagicMock()

    gate_result = MagicMock()
    gate_result.first.return_value = None
    update_result = MagicMock()
    update_result.rowcount = 1

    session.execute = AsyncMock(side_effect=[gate_result, update_result])

    manager = ProposalStateManager(session)

    with patch("will.autonomy.proposal_state_manager.logger", new=MagicMock()):
        await manager.approve(
            proposal_id="prop-123",
            approved_by="governor",
            approval_authority="principal.governor",
            approved_by_original="alice",
        )

    assert session.execute.await_count == 2


import pytest


@pytest.mark.asyncio
# ID: 20716b79-a036-47ba-937e-aa849fcfebc4
async def test_ProposalStateManager_mark_failed():
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    manager = ProposalStateManager(mock_session)

    with patch(
        "will.autonomy.proposal_state_manager.logger.error"
    ) as mock_logger_error:
        await manager.mark_failed("proposal-123", "execution error", {"detail": "boom"})

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
    mock_logger_error.assert_called_once()




# ID: 2af0c3c6-407e-498e-8337-dd7620d5f6db
async def test_ProposalStateManager_mark_finalizing():
    from will.autonomy.proposal_state_manager import ProposalStateManager

    session = MagicMock()
    execute_result = MagicMock()
    execute_result.rowcount = 1
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()

    manager = ProposalStateManager(session)

    with patch(
        "will.autonomy.proposal_state_manager._sanitize_payload",
        MagicMock(return_value={"ok": True}),
    ):
        await manager.mark_finalizing("prop-123", {"output": "done"})

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_service import ProposalService


# ID: fe47edd9-b729-4c8b-ac25-9ddfc01f934f
async def test_ProposalService_reject():
    session = MagicMock()
    proposal_id = "prop-123"
    reason = "not good"

    with (
        patch("will.autonomy.proposal_service.ProposalRepository") as mock_repo_cls,
        patch("will.autonomy.proposal_service.ProposalStateManager") as mock_sm_cls,
        patch(
            "will.autonomy.proposal_service.revive_findings_for_rejected_proposal",
            new_callable=AsyncMock,
        ) as mock_revive,
    ):
        mock_state_manager = MagicMock()
        mock_state_manager.reject = AsyncMock()
        mock_sm_cls.return_value = mock_state_manager

        mock_repository = MagicMock()
        mock_proposal = MagicMock()
        mock_proposal.constitutional_constraints = {"proposal_origin": "autonomous"}
        mock_repository.get = AsyncMock(return_value=mock_proposal)
        mock_repo_cls.return_value = mock_repository

        mock_revive.return_value = {"revived_count": 3}

        service = ProposalService(session)
        result = await service.reject(proposal_id, reason)

        mock_state_manager.reject.assert_awaited_once_with(proposal_id, reason)
        mock_repository.get.assert_awaited_once_with(proposal_id)
        mock_revive.assert_awaited_once_with(
            proposal_id,
            reason,
            {"proposal_origin": "autonomous"},
        )
        assert result == 3





# ID: cdcc3718-c9ae-4fba-9eb5-83d83a7e4bc4
async def test_ProposalService_approve():
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("will.autonomy.proposal_service.ProposalRepository", MagicMock()),
        patch(
            "will.autonomy.proposal_service.ProposalStateManager", MagicMock()
        ) as mock_state_manager_cls,
    ):
        mock_state_manager = mock_state_manager_cls.return_value
        mock_state_manager.approve = AsyncMock()

        service = ProposalService(mock_session)

        await service.approve(
            proposal_id="prop-123",
            approved_by="alice",
            approval_authority="human",
            approved_by_original="bob",
        )

    mock_state_manager.approve.assert_awaited_once_with(
        "prop-123",
        "alice",
        "human",
        approved_by_original="bob",
    )
    mock_session.commit.assert_awaited_once()

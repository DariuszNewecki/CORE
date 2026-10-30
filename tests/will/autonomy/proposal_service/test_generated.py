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


# ID: c8f5dea5-dc7e-4ee1-a32a-601971153aee
async def test_ProposalService_mark_failed() -> None:
    mock_session = MagicMock()
    mock_state_manager = MagicMock()
    mock_state_manager.mark_failed = AsyncMock(return_value=None)

    with (
        patch(
            "will.autonomy.proposal_service.ProposalStateManager",
            return_value=mock_state_manager,
        ),
        patch(
            "will.autonomy.proposal_service.ProposalRepository",
        ),
    ):
        service = ProposalService(mock_session)

        await service.mark_failed("proposal-123", "boom")

    mock_state_manager.mark_failed.assert_awaited_once_with("proposal-123", "boom")


# ID: 479a0ae8-c399-42e4-ab3a-6efa117ef381
async def test_ProposalService_mark_completed():
    session = MagicMock()
    with (
        patch("will.autonomy.proposal_service.ProposalRepository") as MockRepo,
        patch(
            "will.autonomy.proposal_service.ProposalStateManager"
        ) as MockStateManager,
    ):
        mock_state_manager = MagicMock()
        mock_state_manager.mark_completed = AsyncMock(return_value=None)
        MockStateManager.return_value = mock_state_manager

        service = ProposalService(session)

        await service.mark_completed("proposal-123")

        mock_state_manager.mark_completed.assert_awaited_once_with("proposal-123")


from types import SimpleNamespace


# ID: 73aa3ded-e729-476e-adcc-a9630ff60640
async def test_ProposalService_list_pending_approval_paginated():
    session = MagicMock()

    ready_proposal = SimpleNamespace(
        id=1,
        validation_results={"pre_approval_run": True},
    )
    not_ready_proposal = SimpleNamespace(
        id=2,
        validation_results={"pre_approval_run": False},
    )
    no_results_proposal = SimpleNamespace(id=3, validation_results=None)

    service = ProposalService(session)

    with (
        patch("will.autonomy.proposal_service.ProposalRepository") as mock_repo_cls,
        patch("will.autonomy.proposal_service.ProposalStateManager"),
    ):
        mock_repo = MagicMock()
        mock_repo.list_by_status_paginated = AsyncMock(
            return_value=(
                [ready_proposal, not_ready_proposal, no_results_proposal],
                True,
                "cursor-123",
            )
        )
        mock_repo_cls.return_value = mock_repo

        service = ProposalService(session)

        proposals, has_more, cursor = await service.list_pending_approval_paginated(
            limit=10, after_cursor="cursor-000"
        )

    assert proposals == [ready_proposal]
    assert has_more is True
    assert cursor == "cursor-123"
    mock_repo.list_by_status_paginated.assert_awaited_once()

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from will.autonomy.pending_proposal_gate import screen_pending_proposals


@pytest.mark.asyncio
# ID: 24e13935-6ac2-4c9d-8782-96a7d7cd75fb
async def test_screen_pending_proposals():
    proposal_id = uuid4()
    claimed_by = uuid4()
    now = datetime.now(UTC)

    proposal = MagicMock()
    proposal.proposal_id = proposal_id
    proposal.approval_required = True
    proposal.created_at = now
    proposal.validation_results = {}

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    mock_registry = MagicMock()
    mock_registry.session = MagicMock(return_value=session_cm)

    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[proposal])
    mock_repo.update_fields = AsyncMock()

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value={"ok": True})

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository",
            return_value=mock_repo,
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=mock_executor,
        ),
    ):
        outcome = await screen_pending_proposals(
            core_context=MagicMock(), claimed_by=claimed_by, now=now
        )

    assert outcome.passed == [proposal_id]
    assert outcome.failed == []
    assert outcome.expired == []
    mock_executor.execute.assert_awaited_once_with(proposal_id, claimed_by, write=False)



from will.autonomy.pending_proposal_gate import ScreenOutcome


# ID: 8d66e798-0e45-4209-83c2-f78e4a20b0f6
def test_ScreenOutcome_as_payload():
    outcome = MagicMock(spec=ScreenOutcome)
    outcome.passed = 3
    outcome.failed = 1
    outcome.expired = 2

    payload = ScreenOutcome.as_payload(outcome)

    assert payload == {
        "pre_approval_passed": 3,
        "pre_approval_failed": 1,
        "expired": 2,
    }

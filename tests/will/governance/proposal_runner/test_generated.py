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



import pytest

from will.governance.proposal_runner import create_and_score_proposal


@pytest.mark.asyncio
# ID: d96ab2cd-d6d5-41fc-93e9-9745b658586b
async def test_create_and_score_proposal():
    session = MagicMock()
    session.commit = AsyncMock()

    fake_actions = [
        {"action_id": "a1", "flow_id": "f1", "parameters": {"k": "v"}, "order": 0}
    ]

    with (
        patch("will.autonomy.proposal.Proposal") as mock_proposal_cls,
        patch("will.autonomy.proposal.ProposalAction") as mock_action_cls,
        patch("will.autonomy.proposal.ProposalScope") as mock_scope_cls,
        patch("will.autonomy.proposal.ProposalProvenance") as mock_prov_cls,
        patch("will.autonomy.proposal_service.ProposalService") as mock_service_cls,
    ):
        mock_proposal = MagicMock()
        mock_proposal.compute_risk = MagicMock()
        mock_proposal.check_submission = MagicMock(return_value=[])
        mock_proposal.to_dict = MagicMock(return_value={"goal": "g"})
        mock_proposal_cls.return_value = mock_proposal

        mock_scope_cls.return_value = MagicMock()
        mock_prov_cls.return_value = MagicMock()

        mock_service = MagicMock()
        mock_service.create = AsyncMock()
        mock_service_cls.return_value = mock_service

        result = await create_and_score_proposal(
            session,
            goal="g",
            actions=fake_actions,
            files=["src/a.py"],
            created_by="tester",
            write=True,
            anchor_kind="goal",
            anchor_refs=["ref-1"],
            producer="prod",
            retires=["r1"],
        )

    assert result == {"ok": True, "persisted": True, "proposal": {"goal": "g"}}
    mock_proposal.compute_risk.assert_called_once()
    mock_proposal.check_submission.assert_called_once()
    mock_service.create.assert_awaited_once_with(mock_proposal)
    session.commit.assert_awaited_once()
    mock_action_cls.assert_called_once()
    mock_scope_cls.assert_called_once_with(files=["src/a.py"])
    mock_prov_cls.assert_called_once_with(
        anchor_kind="goal",
        anchor_refs=["ref-1"],
        problem_owner="governor",
        producer="prod",
        retires=["r1"],
    )

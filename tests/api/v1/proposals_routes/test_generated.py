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


from api.v1.proposals_routes import approve_proposal


# ID: a9b46510-b755-4949-a2a2-b943448b54e3
async def test_approve_proposal():
    payload = MagicMock()
    payload.approval_authority = "governor"
    user = {"sub": "os-account-123", "principal": "governor"}
    session = MagicMock()

    service_instance = MagicMock()
    service_instance.approve = AsyncMock(return_value=None)

    with patch(
        "api.v1.proposals_routes.ProposalService",
        return_value=service_instance,
    ):
        result = await approve_proposal(
            proposal_id="prop-1",
            payload=payload,
            user=user,
            session=session,
        )

    service_instance.approve.assert_awaited_once_with(
        "prop-1",
        approved_by="governor",
        approval_authority="governor",
        approved_by_original="os-account-123",
    )
    assert result == {
        "ok": True,
        "proposal_id": "prop-1",
        "status": "approved",
        "approved_by": "governor",
        "approved_by_original": "os-account-123",
        "approval_authority": "governor",
    }


import pytest

from api.v1.proposals_routes import get_proposal


@pytest.mark.asyncio
# ID: 8c91b5f4-5fd3-49f7-9e8a-1410e4c7c15f
async def test_get_proposal():
    session = MagicMock()

    proposal = MagicMock()
    proposal.to_dict.return_value = {"id": "prop-1", "name": "test"}

    service = MagicMock()
    service.get = AsyncMock(return_value=proposal)

    with patch(
        "api.v1.proposals_routes.ProposalService", return_value=service
    ) as mock_service_cls:
        result = await get_proposal("prop-1", session=session)

    mock_service_cls.assert_called_once_with(session)
    service.get.assert_awaited_once_with("prop-1")
    proposal.to_dict.assert_called_once_with()
    assert result == {"id": "prop-1", "name": "test"}


import asyncio

from api.v1.proposals_routes import get_proposal_chain


# ID: aec2e524-d96d-4aeb-a440-bdc58d3482b4
def test_get_proposal_chain():
    proposal_id = "prop-123"
    expected_chain = {"proposal_id": proposal_id, "steps": [{"step": 1}, {"step": 2}]}

    svc = MagicMock()
    svc.get_chain_for_proposal = AsyncMock(return_value=expected_chain)

    session = MagicMock()

    result = asyncio.run(get_proposal_chain(proposal_id, svc, session))

    assert result == expected_chain
    svc.get_chain_for_proposal.assert_awaited_once_with(proposal_id, session)


import pytest

from api.v1.proposals_routes import list_proposals


@pytest.mark.asyncio
# ID: 8f601ac6-65af-4d36-8055-8507376c3e80
async def test_list_proposals():
    fake_proposal = MagicMock()
    fake_proposal.to_dict.return_value = {"id": "p1", "status": "pending"}

    service_mock = MagicMock()
    service_mock.list_pending_approval_paginated = AsyncMock(
        return_value=([fake_proposal], True, "cursor-1")
    )

    with patch(
        "api.v1.proposals_routes.ProposalService", return_value=service_mock
    ) as service_cls:
        result = await list_proposals(
            status=None, limit=50, after=None, session=MagicMock()
        )

    service_cls.assert_called_once()
    service_mock.list_pending_approval_paginated.assert_awaited_once_with(
        limit=50, after_cursor=None
    )
    assert result == {
        "count": 1,
        "has_more": True,
        "next_cursor": "cursor-1",
        "proposals": [{"id": "p1", "status": "pending"}],
    }


from api.v1.proposals_routes import create_proposal


# ID: 8c27de3f-743e-4177-879a-813a1d5b5784
def test_create_proposal():
    payload = MagicMock()
    payload.goal = "reduce risk"
    payload.actions = ["a1", "a2"]
    payload.files = ["f1.py"]
    payload.created_by = "tester"
    payload.write = True
    payload.anchor_kind = "symbol"
    payload.anchor_refs = ["foo"]
    payload.producer = "agent"
    payload.retires = []

    session = MagicMock()

    expected = {"ok": True, "proposal": {"id": "p1"}}

    mock_create_and_score = AsyncMock(return_value=expected)

    with patch(
        "api.v1.proposals_routes.create_and_score_proposal",
        mock_create_and_score,
    ):
        result = asyncio.run(create_proposal(payload, session))

    assert result == expected
    mock_create_and_score.assert_awaited_once_with(
        session,
        goal="reduce risk",
        actions=["a1", "a2"],
        files=["f1.py"],
        created_by="tester",
        write=True,
        anchor_kind="symbol",
        anchor_refs=["foo"],
        producer="agent",
        retires=[],
    )



from api.v1.proposals_routes import submit_change


# ID: 89cc44ec-d899-411a-8b97-3271c2c030a9
def test_submit_change():
    payload = MagicMock()
    payload.patch = "--- a\n+++ b\n"
    payload.validation_run_id = "vr-123"
    payload.goal = "goal-1"
    payload.anchor_kind = "symbol"
    payload.anchor_refs = ["ref-1"]
    payload.producer = "producer-x"
    payload.retires = []

    expected = {"submission_id": "sub-1", "status": "accepted"}

    with patch(
        "will.autonomy.producer_submission.submit_producer_change",
        new=AsyncMock(return_value=expected),
    ) as mock_submit:
        result = asyncio.run(submit_change(payload))

    assert result == expected
    mock_submit.assert_awaited_once_with(
        patch="--- a\n+++ b\n",
        validation_run_id="vr-123",
        goal="goal-1",
        anchor_kind="symbol",
        anchor_refs=["ref-1"],
        producer="producer-x",
        retires=[],
        created_by="api.proposals_submit",
    )

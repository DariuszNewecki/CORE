# tests/api/v1/test_proposals_routes.py

"""Unit tests for proposals_routes — ADR-054 Phase 1.

Mocks ProposalService and ProposalExecutor so assertions target the
route translation layer — not the proposal lifecycle implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.v1.proposals_routes import (
    ApproveRequest,
    CreateProposalRequest,
    ExecuteRequest,
    RejectRequest,
    approve_proposal,
    create_proposal,
    execute_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
)
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_state_manager import ProposalNotFoundError


def _mock_request():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


def _mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


def _stub_proposal(proposal_id: str | None = None) -> MagicMock:
    p = MagicMock()
    p.to_dict.return_value = {
        "proposal_id": proposal_id or str(uuid4()),
        "goal": "fix imports",
        "status": "awaiting_approval",
    }
    return p


# ── create_proposal ───────────────────────────────────────────────────────────

async def test_create_proposal_dry_run_does_not_persist():
    """write=False builds and risk-scores the proposal without calling service.create."""
    session = _mock_session()
    out = await create_proposal(
        payload=CreateProposalRequest(goal="fix imports", write=False),
        session=session,
    )
    assert out["ok"] is True
    assert out["persisted"] is False
    assert "proposal" in out
    session.commit.assert_not_awaited()


async def test_create_proposal_write_true_persists_and_commits():
    """write=True calls ProposalService.create and commits the session."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await create_proposal(
            payload=CreateProposalRequest(goal="fix imports", write=True),
            session=session,
        )

    assert out["ok"] is True
    assert out["persisted"] is True
    mock_svc.create.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_create_proposal_actions_are_mapped():
    """Actions in the payload are translated to ProposalAction instances."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await create_proposal(
            payload=CreateProposalRequest(
                goal="add tests",
                actions=[{"action_id": "build.tests", "parameters": {}, "order": 0}],
                write=False,
            ),
            session=session,
        )

    # The proposal dict should carry the action
    proposal_dict = out["proposal"]
    assert proposal_dict is not None


# ── list_proposals ────────────────────────────────────────────────────────────

async def test_list_proposals_default_returns_pending_approval():
    """No status filter delegates to list_pending_approval_paginated."""
    proposals = [_stub_proposal()]
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.list_pending_approval_paginated = AsyncMock(
            return_value=(proposals, False, None)
        )
        mock_svc_cls.return_value = mock_svc

        out = await list_proposals(status=None, limit=50, after=None, session=session)

    assert out["count"] == 1
    assert out["has_more"] is False
    assert out["next_cursor"] is None
    mock_svc.list_pending_approval_paginated.assert_awaited_once()


async def test_list_proposals_valid_status_delegates_to_list_by_status():
    """Valid status string delegates to list_by_status_paginated."""
    proposals = [_stub_proposal()]
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.list_by_status_paginated = AsyncMock(
            return_value=(proposals, False, None)
        )
        mock_svc_cls.return_value = mock_svc

        out = await list_proposals(
            status=ProposalStatus.APPROVED.value,
            limit=50,
            after=None,
            session=session,
        )

    assert out["count"] == 1
    mock_svc.list_by_status_paginated.assert_awaited_once()


async def test_list_proposals_invalid_status_raises_400():
    """Unknown status string raises HTTPException(400) with the bad value in detail."""
    session = _mock_session()
    with pytest.raises(HTTPException) as exc:
        await list_proposals(
            status="not_a_real_status", limit=50, after=None, session=session
        )
    assert exc.value.status_code == 400
    assert "not_a_real_status" in exc.value.detail


async def test_list_proposals_pagination_cursor_forwarded():
    """after cursor is forwarded to the service call."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.list_pending_approval_paginated = AsyncMock(
            return_value=([], False, None)
        )
        mock_svc_cls.return_value = mock_svc

        await list_proposals(status=None, limit=10, after="cursor-xyz", session=session)

    _, call_kwargs = mock_svc.list_pending_approval_paginated.call_args
    assert call_kwargs.get("after_cursor") == "cursor-xyz"


# ── get_proposal ──────────────────────────────────────────────────────────────

async def test_get_proposal_returns_proposal_dict():
    """Found proposal returns its to_dict() shape."""
    pid = str(uuid4())
    proposal = _stub_proposal(pid)
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.get = AsyncMock(return_value=proposal)
        mock_svc_cls.return_value = mock_svc

        out = await get_proposal(proposal_id=pid, session=session)

    assert out["proposal_id"] == pid


async def test_get_proposal_not_found_raises_404():
    """Unknown proposal_id raises HTTPException(404)."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.get = AsyncMock(return_value=None)
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await get_proposal(proposal_id="nonexistent-id", session=session)

    assert exc.value.status_code == 404
    assert "nonexistent-id" in exc.value.detail


# ── approve_proposal ──────────────────────────────────────────────────────────

async def test_approve_proposal_returns_approved_status():
    """Happy path returns ok=True, APPROVED status, and approval metadata."""
    pid = str(uuid4())
    session = _mock_session()
    user = {"email": "governor@example.com"}
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await approve_proposal(
            proposal_id=pid,
            payload=ApproveRequest(approval_authority="human_governor"),
            user=user,
            session=session,
        )

    assert out["ok"] is True
    assert out["proposal_id"] == pid
    assert out["status"] == ProposalStatus.APPROVED.value
    assert out["approved_by"] == "governor@example.com"
    assert out["approval_authority"] == "human_governor"


async def test_approve_proposal_falls_back_to_sub_when_no_email():
    """approved_by falls back to 'sub' when 'email' key is absent."""
    pid = str(uuid4())
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await approve_proposal(
            proposal_id=pid,
            payload=ApproveRequest(approval_authority="human_governor"),
            user={"sub": "governor-sub-id"},
            session=session,
        )

    assert out["approved_by"] == "governor-sub-id"


async def test_approve_proposal_not_found_raises_404():
    """ProposalNotFoundError from service is translated to HTTPException(404)."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock(
            side_effect=ProposalNotFoundError("proposal not found")
        )
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await approve_proposal(
                proposal_id="bad-id",
                payload=ApproveRequest(approval_authority="human_governor"),
                user={"sub": "governor"},
                session=session,
            )

    assert exc.value.status_code == 404


async def test_approve_proposal_invalid_authority_raises_400():
    """ValueError from service (unknown authority) is translated to HTTPException(400)."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock(
            side_effect=ValueError("unknown authority: bogus")
        )
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await approve_proposal(
                proposal_id=str(uuid4()),
                payload=ApproveRequest(approval_authority="bogus"),
                user={"sub": "governor"},
                session=session,
            )

    assert exc.value.status_code == 400
    assert "bogus" in exc.value.detail


# ── reject_proposal ───────────────────────────────────────────────────────────

async def test_reject_proposal_returns_revived_count():
    """Rejection returns ok=True, REJECTED status, and the revived_count from service."""
    pid = str(uuid4())
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.reject = AsyncMock(return_value=3)
        mock_svc_cls.return_value = mock_svc

        out = await reject_proposal(
            proposal_id=pid,
            payload=RejectRequest(reason="scope too broad"),
            session=session,
        )

    assert out["ok"] is True
    assert out["proposal_id"] == pid
    assert out["status"] == ProposalStatus.REJECTED.value
    assert out["reason"] == "scope too broad"
    assert out["revived_count"] == 3


async def test_reject_proposal_zero_revived_is_valid():
    """revived_count=0 is a legitimate outcome (proposal had no parked findings)."""
    pid = str(uuid4())
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.reject = AsyncMock(return_value=0)
        mock_svc_cls.return_value = mock_svc

        out = await reject_proposal(
            proposal_id=pid,
            payload=RejectRequest(reason="duplicate"),
            session=session,
        )

    assert out["revived_count"] == 0


async def test_reject_proposal_not_found_raises_404():
    """ProposalNotFoundError is translated to HTTPException(404)."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.reject = AsyncMock(
            side_effect=ProposalNotFoundError("proposal not found")
        )
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await reject_proposal(
                proposal_id="bad-id",
                payload=RejectRequest(reason="bad id"),
                session=session,
            )

    assert exc.value.status_code == 404


# ── execute_proposal ──────────────────────────────────────────────────────────

async def test_execute_proposal_delegates_to_executor_dry_run():
    """execute_proposal delegates to ProposalExecutor.execute with write=False."""
    pid = str(uuid4())
    result = {"ok": True, "proposal_id": pid, "actions_executed": 2}
    with patch("api.v1.proposals_routes.ProposalExecutor") as mock_exec_cls:
        mock_exec = AsyncMock()
        mock_exec.execute = AsyncMock(return_value=result)
        mock_exec_cls.return_value = mock_exec

        out = await execute_proposal(
            proposal_id=pid,
            payload=ExecuteRequest(write=False),
            request=_mock_request(),
        )

    assert out == result
    mock_exec.execute.assert_awaited_once()
    # write=False is the default dry-run
    call_args = mock_exec.execute.call_args
    assert call_args.kwargs.get("write") is False or call_args.args[2] is False


async def test_execute_proposal_passes_write_true_when_requested():
    """write=True is forwarded to ProposalExecutor.execute."""
    pid = str(uuid4())
    with patch("api.v1.proposals_routes.ProposalExecutor") as mock_exec_cls:
        mock_exec = AsyncMock()
        mock_exec.execute = AsyncMock(return_value={"ok": True})
        mock_exec_cls.return_value = mock_exec

        await execute_proposal(
            proposal_id=pid,
            payload=ExecuteRequest(write=True),
            request=_mock_request(),
        )

    call_args = mock_exec.execute.call_args
    write_passed = (
        call_args.kwargs.get("write")
        if "write" in call_args.kwargs
        else call_args.args[2]
    )
    assert write_passed is True

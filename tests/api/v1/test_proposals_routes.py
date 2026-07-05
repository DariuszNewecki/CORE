# tests/api/v1/test_proposals_routes.py

"""Unit tests for proposals_routes — ADR-054 Phase 1 (#335).

Covers GET list (with status filter), GET single, POST approve,
POST reject, POST execute. Mocks ProposalService and ProposalExecutor;
sessions are mocked AsyncSession instances.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.v1.proposals_routes import (
    API_CLAIMER_UUID,
    ApproveRequest,
    ExecuteRequest,
    RejectRequest,
    approve_proposal,
    execute_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
    router,
)
from will.autonomy.proposal_state_manager import ProposalNotFoundError


def _mk_proposal_dict(pid: str = "p-1", status: str = "pending_approval") -> dict:
    return {
        "proposal_id": pid,
        "status": status,
        "goal": "demo",
        "actions": [],
        "scope": {"files": [], "modules": [], "symbols": []},
        "created_by": "test",
    }


async def test_list_proposals_no_status_returns_pending_approval():
    """No status filter → service.list_pending_approval is called and the
    response wraps proposals in {count, proposals}."""
    session = AsyncMock()

    fake_proposal = MagicMock()
    fake_proposal.to_dict = MagicMock(return_value=_mk_proposal_dict())

    service = AsyncMock()
    service.list_pending_approval_paginated = AsyncMock(
        return_value=([fake_proposal], False, None)
    )
    service.list_by_status_paginated = AsyncMock()

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await list_proposals(status=None, limit=50, session=session)

    assert out["count"] == 1
    assert out["proposals"] == [_mk_proposal_dict()]
    service.list_pending_approval_paginated.assert_awaited_once()
    service.list_by_status_paginated.assert_not_called()


async def test_list_proposals_with_status_filter_calls_list_by_status():
    """Valid status filter → service.list_by_status is called with the
    parsed enum value."""
    session = AsyncMock()

    fake_proposal = MagicMock()
    fake_proposal.to_dict = MagicMock(return_value=_mk_proposal_dict(status="approved"))

    service = AsyncMock()
    service.list_pending_approval_paginated = AsyncMock()
    service.list_by_status_paginated = AsyncMock(
        return_value=([fake_proposal], False, None)
    )

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await list_proposals(status="approved", limit=20, session=session)

    assert out["count"] == 1
    service.list_by_status_paginated.assert_awaited_once()
    service.list_pending_approval_paginated.assert_not_called()


async def test_list_proposals_invalid_status_raises_400():
    """Unknown status string raises HTTPException(400)."""
    session = AsyncMock()

    with patch("api.v1.proposals_routes.ProposalService", return_value=AsyncMock()):
        with pytest.raises(HTTPException) as exc_info:
            await list_proposals(status="not_a_status", limit=50, session=session)

    assert exc_info.value.status_code == 400
    assert "not_a_status" in exc_info.value.detail


async def test_get_proposal_returns_to_dict():
    """GET /{id} returns proposal.to_dict()."""
    session = AsyncMock()

    fake_proposal = MagicMock()
    fake_proposal.to_dict = MagicMock(return_value=_mk_proposal_dict())

    service = AsyncMock()
    service.get = AsyncMock(return_value=fake_proposal)

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await get_proposal(proposal_id="p-1", session=session)

    assert out == _mk_proposal_dict()
    service.get.assert_awaited_once_with("p-1")


async def test_get_proposal_not_found_returns_404():
    """Missing proposal raises HTTPException(404)."""
    session = AsyncMock()

    service = AsyncMock()
    service.get = AsyncMock(return_value=None)

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await get_proposal(proposal_id="missing", session=session)

    assert exc_info.value.status_code == 404


async def test_approve_proposal_derives_approved_by_from_jwt():
    """approve_proposal derives approved_by from the JWT user dict (email
    preferred, sub as fallback) — body carries no identity claim.
    Returns governed status payload with approval_authority forwarded."""
    session = AsyncMock()

    service = AsyncMock()
    service.approve = AsyncMock()

    payload = ApproveRequest(approval_authority="governor_direct")
    user = {"sub": "uid-123", "email": "admin@example.com", "role": "platform_admin"}

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await approve_proposal(
            proposal_id="p-1", payload=payload, user=user, session=session
        )

    service.approve.assert_awaited_once_with(
        "p-1",
        approved_by="admin@example.com",
        approval_authority="governor_direct",
    )
    assert out["ok"] is True
    assert out["proposal_id"] == "p-1"
    assert out["status"] == "approved"
    assert out["approved_by"] == "admin@example.com"
    assert out["approval_authority"] == "governor_direct"


async def test_approve_proposal_falls_back_to_sub_when_no_email():
    """When JWT has no email, approved_by falls back to the sub claim."""
    session = AsyncMock()

    service = AsyncMock()
    service.approve = AsyncMock()

    payload = ApproveRequest(approval_authority="governor_direct")
    user = {"sub": "uuid-456", "email": None, "role": "platform_admin"}

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await approve_proposal(
            proposal_id="p-2", payload=payload, user=user, session=session
        )

    service.approve.assert_awaited_once_with(
        "p-2",
        approved_by="uuid-456",
        approval_authority="governor_direct",
    )
    assert out["approved_by"] == "uuid-456"


async def test_approve_proposal_unknown_id_returns_404():
    """ProposalNotFoundError → HTTPException(404)."""
    session = AsyncMock()

    service = AsyncMock()
    service.approve = AsyncMock(side_effect=ProposalNotFoundError("missing"))

    payload = ApproveRequest(approval_authority="governor_direct")
    user = {"sub": "uid", "email": "g@test.com", "role": "platform_admin"}

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await approve_proposal(
                proposal_id="missing", payload=payload, user=user, session=session
            )

    assert exc_info.value.status_code == 404


async def test_approve_proposal_bad_authority_returns_400():
    """ValueError from state manager → HTTPException(400)."""
    session = AsyncMock()

    service = AsyncMock()
    service.approve = AsyncMock(side_effect=ValueError("bad authority"))

    payload = ApproveRequest(approval_authority="bogus")
    user = {"sub": "uid", "email": "g@test.com", "role": "platform_admin"}

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await approve_proposal(
                proposal_id="p-1", payload=payload, user=user, session=session
            )

    assert exc_info.value.status_code == 400


async def test_reject_proposal_returns_revived_count():
    """reject_proposal forwards reason and returns revived_count from
    service.reject (ADR-010 §7a / ADR-045 finding revival)."""
    session = AsyncMock()

    service = AsyncMock()
    service.reject = AsyncMock(return_value=3)

    payload = RejectRequest(reason="stale finding")

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        out = await reject_proposal(proposal_id="p-1", payload=payload, session=session)

    service.reject.assert_awaited_once_with("p-1", reason="stale finding")
    assert out == {
        "ok": True,
        "proposal_id": "p-1",
        "status": "rejected",
        "reason": "stale finding",
        "revived_count": 3,
    }


async def test_reject_proposal_unknown_id_returns_404():
    """ProposalNotFoundError from service.reject → 404."""
    session = AsyncMock()

    service = AsyncMock()
    service.reject = AsyncMock(side_effect=ProposalNotFoundError("nope"))

    payload = RejectRequest(reason="anything")

    with patch("api.v1.proposals_routes.ProposalService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await reject_proposal(proposal_id="nope", payload=payload, session=session)

    assert exc_info.value.status_code == 404


async def test_execute_proposal_uses_api_claimer_and_returns_executor_result():
    """execute_proposal builds ProposalExecutor with core_context, calls
    .execute with API_CLAIMER_UUID + write flag, and passes the result back."""
    request = MagicMock(spec=Request)
    request.app.state.core_context = MagicMock()

    payload = ExecuteRequest(write=True)
    executor_result = {"ok": True, "executed": True, "proposal_id": "p-1"}

    executor = MagicMock()
    executor.execute = AsyncMock(return_value=executor_result)

    with patch(
        "api.v1.proposals_routes.ProposalExecutor", return_value=executor
    ) as mock_cls:
        out = await execute_proposal(
            proposal_id="p-1", payload=payload, request=request
        )

    mock_cls.assert_called_once_with(request.app.state.core_context)
    executor.execute.assert_awaited_once_with("p-1", API_CLAIMER_UUID, write=True)
    assert out == executor_result


async def test_execute_proposal_dry_run_default():
    """Default ExecuteRequest is write=False; executor.execute receives
    write=False."""
    request = MagicMock(spec=Request)
    request.app.state.core_context = MagicMock()

    payload = ExecuteRequest()  # default write=False
    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"ok": True})

    with patch("api.v1.proposals_routes.ProposalExecutor", return_value=executor):
        await execute_proposal(proposal_id="p-1", payload=payload, request=request)

    executor.execute.assert_awaited_once_with("p-1", API_CLAIMER_UUID, write=False)


# ---------------------------------------------------------------------------
# RBAC route-level tests — #707
# ---------------------------------------------------------------------------


def _make_proposals_client(role: str) -> TestClient:
    """Build a minimal FastAPI test client with the proposals router and a
    mocked get_current_user that returns the given role."""
    app = FastAPI()
    app.include_router(router)

    async def _mock_user() -> dict:
        return {"sub": "u1", "email": "u@test.com", "role": role}

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


def test_create_proposal_non_admin_receives_403() -> None:
    """POST / (create proposal) requires platform_admin — visitor gets 403."""
    client = _make_proposals_client(role="visitor")
    r = client.post("/proposals/", json={"goal": "test"})
    assert r.status_code == 403


def test_reject_proposal_non_admin_receives_403() -> None:
    """POST /{id}/reject requires platform_admin — visitor gets 403."""
    client = _make_proposals_client(role="visitor")
    r = client.post("/proposals/some-id/reject", json={"reason": "stale"})
    assert r.status_code == 403

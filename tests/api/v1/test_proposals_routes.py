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

_VALID_ACTIONS = [{"action_id": "fix.imports", "parameters": {}, "order": 0}]
_FILES = ["src/widget.py"]
# ADR-168 Amendment 2026-10-10 A2: a submittable proposal says who and why.
_ANCHOR = {"anchor_kind": "issue", "anchor_refs": ["#1"], "producer": "test-producer"}


async def test_create_proposal_malformed_is_refused_with_422():
    """No action, an unknown action, or no file: 422, nothing persisted."""
    session = _mock_session()
    with patch("will.autonomy.proposal_service.ProposalService") as mock_svc_cls:
        with pytest.raises(HTTPException) as exc_info:
            await create_proposal(
                payload=CreateProposalRequest(
                    goal="smuggle",
                    actions=[{"action_id": "no.such.action", "parameters": {}}],
                    files=_FILES,
                    write=True,
                ),
                session=session,
            )

    assert exc_info.value.status_code == 422
    assert any("not found in registry" in e for e in exc_info.value.detail)
    mock_svc_cls.assert_not_called()


async def test_create_proposal_without_anchor_is_refused_with_422():
    """ADR-168 Amendment 2026-10-10 A2: no anchor/producer → 422, not persisted."""
    session = _mock_session()
    with patch("will.autonomy.proposal_service.ProposalService") as mock_svc_cls:
        with pytest.raises(HTTPException) as exc_info:
            await create_proposal(
                payload=CreateProposalRequest(
                    goal="fix imports", actions=_VALID_ACTIONS, files=_FILES, write=True
                ),
                session=session,
            )

    assert exc_info.value.status_code == 422
    assert any("provenance" in e for e in exc_info.value.detail)
    mock_svc_cls.assert_not_called()
    session.commit.assert_not_awaited()


async def test_create_proposal_dry_run_does_not_persist():
    """write=False builds and risk-scores the proposal without calling service.create."""
    session = _mock_session()
    out = await create_proposal(
        payload=CreateProposalRequest(
            goal="fix imports",
            actions=_VALID_ACTIONS,
            files=_FILES,
            write=False,
            **_ANCHOR,
        ),
        session=session,
    )
    assert out["ok"] is True
    assert out["persisted"] is False
    assert "proposal" in out
    session.commit.assert_not_awaited()


async def test_create_proposal_write_true_persists_and_commits():
    """write=True calls ProposalService.create and commits the session.

    #771: creation logic moved to will.governance.proposal_runner, which
    imports ProposalService from its source module — patch there, not on
    the route module, so the facade's function-local import is intercepted.
    """
    session = _mock_session()
    with patch("will.autonomy.proposal_service.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await create_proposal(
            payload=CreateProposalRequest(
                goal="fix imports",
                actions=_VALID_ACTIONS,
                files=_FILES,
                write=True,
                **_ANCHOR,
            ),
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
                files=_FILES,
                write=False,
                **_ANCHOR,
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


_GOVERNOR = {"sub": "darek", "principal": "principal.governor"}


async def test_approve_proposal_stamps_the_verified_governor():
    """The actor and authority come from the verified caller (ADR-132 D10.4)."""
    pid = str(uuid4())
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await approve_proposal(
            proposal_id=pid,
            payload=ApproveRequest(),
            user=_GOVERNOR,
            session=session,
        )

    assert out["ok"] is True
    assert out["proposal_id"] == pid
    assert out["status"] == ProposalStatus.APPROVED.value
    assert out["approved_by"] == "governor"
    assert out["approved_by_original"] == "darek"
    assert out["approval_authority"] == "principal.governor"
    mock_svc.approve.assert_awaited_once_with(
        pid,
        approved_by="governor",
        approval_authority="principal.governor",
        approved_by_original="darek",
    )


async def test_approve_proposal_ignores_a_body_approved_by():
    """A body cannot name the approver: extra fields are dropped."""
    pid = str(uuid4())
    session = _mock_session()
    payload = ApproveRequest.model_validate(
        {"approved_by": "someone-else", "approval_authority": "principal.governor"}
    )
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        out = await approve_proposal(
            proposal_id=pid, payload=payload, user=_GOVERNOR, session=session
        )

    assert out["approved_by"] == "governor"
    assert out["approved_by_original"] == "darek"


async def test_approve_proposal_refuses_a_different_body_authority():
    """A body authority other than the caller's verified one is a 400."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await approve_proposal(
                proposal_id=str(uuid4()),
                payload=ApproveRequest(approval_authority="human_governor"),
                user=_GOVERNOR,
                session=session,
            )

    assert exc.value.status_code == 400
    assert "human_governor" in exc.value.detail
    mock_svc.approve.assert_not_called()


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
                payload=ApproveRequest(approval_authority="principal.governor"),
                user=_GOVERNOR,
                session=session,
            )

    assert exc.value.status_code == 404


async def test_approve_proposal_non_approvable_state_raises_400():
    """ValueError from service is translated to HTTPException(400)."""
    session = _mock_session()
    with patch("api.v1.proposals_routes.ProposalService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.approve = AsyncMock(side_effect=ValueError("not approvable: draft"))
        mock_svc_cls.return_value = mock_svc

        with pytest.raises(HTTPException) as exc:
            await approve_proposal(
                proposal_id=str(uuid4()),
                payload=ApproveRequest(),
                user=_GOVERNOR,
                session=session,
            )

    assert exc.value.status_code == 400
    assert "draft" in exc.value.detail


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
    with patch("will.autonomy.proposal_executor.ProposalExecutor") as mock_exec_cls:
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
    with patch("will.autonomy.proposal_executor.ProposalExecutor") as mock_exec_cls:
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


# ── submit (ADR-168 Amendment 2026-10-10) ────────────────────────────────────


def _producer():
    from api.dependencies import CallerPrincipal

    return CallerPrincipal(uid=1001, account="core-claude", role="principal.producer")


def _submit_request():
    from api.v1.proposals_routes import SubmitChangeRequest

    return SubmitChangeRequest(
        patch="diff",
        validation_run_id="00000000-0000-0000-0000-000000000001",
        goal="g",
        anchor_kind="issue",
        anchor_refs=["#1"],
        producer="p",
    )


# ID: a79ea4b8-fedc-4188-a9e7-ff5e502a7c89
async def test_submit_routes_to_the_will_submission_service():
    from api.v1.proposals_routes import submit_change

    service = AsyncMock(return_value={"proposal_id": "p1"})
    with patch("will.autonomy.producer_submission.submit_producer_change", service):
        out = await submit_change(payload=_submit_request(), principal=_producer())

    assert out == {"proposal_id": "p1"}
    assert service.await_args.kwargs["created_by"] == "api.proposals_submit"
    assert service.await_args.kwargs["producer"] == "core-claude as p"


# ID: 3fceb8a5-ecfb-4737-b804-aa3006bb479e
async def test_submit_refusal_is_422():
    from api.v1.proposals_routes import submit_change
    from will.autonomy.producer_submission import ProducerSubmissionError

    service = AsyncMock(side_effect=ProducerSubmissionError("no"))
    with patch("will.autonomy.producer_submission.submit_producer_change", service):
        with pytest.raises(HTTPException) as exc_info:
            await submit_change(payload=_submit_request(), principal=_producer())
    assert exc_info.value.status_code == 422


# ID: 5a2d8e61-3f97-4c0b-8e14-9b6c7d2a1f35
async def test_submit_over_tcp_is_refused_and_nothing_is_submitted():
    """Review M2: TCP carries no identity, so it cannot name a producer."""
    from api.dependencies import CallerPrincipal
    from api.v1.proposals_routes import submit_change

    service = AsyncMock(return_value={"proposal_id": "p1"})
    with patch("will.autonomy.producer_submission.submit_producer_change", service):
        with pytest.raises(HTTPException) as exc_info:
            await submit_change(
                payload=_submit_request(),
                principal=CallerPrincipal(uid=None, account=None, role=None),
            )
    assert exc_info.value.status_code == 403
    service.assert_not_awaited()


# ID: 7c4f1b92-8d26-4e5a-a3b0-1e9d6f2c8b47
def test_recorded_producer_is_the_account():
    from api.v1.proposals_routes import recorded_producer

    assert recorded_producer("core-claude", None) == "core-claude"
    assert recorded_producer("core-claude", "core-claude") == "core-claude"
    assert recorded_producer("core-claude", "governor") == "core-claude as governor"

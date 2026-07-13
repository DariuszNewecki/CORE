# src/api/v1/proposals_routes.py

"""
Proposals API endpoints (ADR-054 Phase 1).

Surfaces the core.autonomous_proposals state machine over HTTP so the
CLI (and other governor-direct clients) can migrate off direct
`will.*` / `shared.*` imports. The semantics — approval authority
closed-set, claim sentinel, dry-run vs write — are unchanged from the
CLI path; this module is a thin translation layer.

CONSTITUTIONAL:
- Session access goes through api.dependencies.get_api_session only.
- Domain construction (Proposal/ProposalScope + compute_risk) and
  ProposalExecutor invocation route through the will.governance.
  proposal_runner facade (ADR-049 D1 architectural-debt closure, #771) —
  mirroring the fix_runner / sync_runner pattern the /fix and /sync
  surfaces use. Read/lifecycle endpoints delegate to ProposalService /
  ConsequenceLogService facades.
- CoreContext is read from request.app.state.core_context — never
  constructed in routes.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_api_session,
    get_consequence_log_service,
    require_governor,
)
from api.v1.schemas import GovernanceChainResponse, ProposalResponse
from body.services.consequence_log_service import ConsequenceLogService
from shared.context import CoreContext
from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_service import ProposalService
from will.autonomy.proposal_state_manager import ProposalNotFoundError
from will.governance.proposal_runner import (
    create_and_score_proposal,
    execute_proposal_direct,
)


logger = getLogger(__name__)


# API claimer sentinel for governor-direct execution paths invoked over HTTP.
# Mirrors the ADR-017 D4 pattern: governor-direct execution paths get a stable
# sentinel so claimed_by lineage is queryable per surface.
API_CLAIMER_UUID: Final[UUID] = UUID("00000000-0000-0000-0000-000000000002")


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/proposals")


# ID: 5103629b-96d2-4c2c-8217-df99555ed221
class ApproveRequest(BaseModel):
    """Body for POST /proposals/{id}/approve.

    `approved_by` is derived server-side from the request context and is
    not accepted from the request body.
    """

    approval_authority: str


# ID: 3a74ddce-87c2-4528-a2f4-5ec68d171ea0
class RejectRequest(BaseModel):
    """Body for POST /proposals/{id}/reject."""

    reason: str


# ID: 57020012-ad90-461f-98d3-50f565b65294
class ExecuteRequest(BaseModel):
    """Body for POST /proposals/{id}/execute."""

    write: bool = False


# ID: 71caa34a-1661-4178-b982-626bff254539
class CreateProposalRequest(BaseModel):
    """Body for POST /proposals.

    `write=False` is a dry-run: server builds the Proposal and computes
    risk but does not persist. `write=True` persists via
    ProposalService.create.
    """

    goal: str
    actions: list[dict] = []
    files: list[str] = []
    created_by: str = "cli_operator"
    write: bool = True


@router.post(
    "",
    status_code=201,
    summary="Create a proposal",
    dependencies=[require_governor],
    description=(
        "Build a proposal from a goal + action sequence, compute its risk, "
        "and (when `write=true`) persist it via ProposalService. With "
        "`write=false` (default) the proposal is constructed and "
        "risk-scored in-memory but NOT written to the database — useful for "
        "dry-run validation. Returns the proposal's `to_dict()` shape either way."
    ),
)
# ID: 9704145a-25f5-460c-81a9-fe1fa0b47d68
async def create_proposal(
    payload: CreateProposalRequest,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Create a new proposal.

    Validates the action sequence, computes risk, and (when write=True)
    persists via ProposalService.create. Returns the proposal's
    `to_dict()` representation either way; in dry-run mode the row
    is not flushed to the database. Domain construction + scoring lives
    in the will.governance.proposal_runner facade (#771).
    """
    return await create_and_score_proposal(
        session,
        goal=payload.goal,
        actions=payload.actions,
        files=payload.files,
        created_by=payload.created_by,
        write=payload.write,
    )


@router.get(
    "",
    summary="List proposals",
    dependencies=[require_governor],
    description=(
        "List proposals, optionally filtered by `status`. When `status` is "
        "omitted, returns proposals awaiting approval. `limit` is capped at 500. "
        "Pass `after=<next_cursor>` from a previous response to advance the page. "
        "F-34 (web dashboard) consumes this endpoint to render the proposal queue."
    ),
)
# ID: b6575d68-b902-4071-8497-76b053430fec
async def list_proposals(
    status: str | None = Query(None, description="ProposalStatus value to filter by."),
    limit: int = Query(50, ge=1, le=500),
    after: str | None = Query(
        None, description="Keyset cursor from a previous response."
    ),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """List proposals, optionally filtered by status.

    When `status` is omitted, returns proposals awaiting approval.
    Returns `has_more` and `next_cursor` for keyset pagination.
    """
    service = ProposalService(session)

    if status is None:
        (
            proposals,
            has_more,
            next_cursor,
        ) = await service.list_pending_approval_paginated(
            limit=limit, after_cursor=after
        )
    else:
        try:
            parsed = ProposalStatus(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid status {status!r}; allowed: "
                    f"{[s.value for s in ProposalStatus]}"
                ),
            ) from exc
        proposals, has_more, next_cursor = await service.list_by_status_paginated(
            parsed, limit=limit, after_cursor=after
        )

    return {
        "count": len(proposals),
        "has_more": has_more,
        "next_cursor": next_cursor,
        "proposals": [p.to_dict() for p in proposals],
    }


@router.get(
    "/{proposal_id}/chain",
    response_model=GovernanceChainResponse,
    summary="Governance chain for a proposal",
    dependencies=[require_governor],
    description=(
        "Return the complete governance chain for a proposal: the proposal "
        "itself, every linked finding (detected violations), and the execution "
        "consequence (files changed, git SHAs). `consequence` is null when the "
        "proposal has not yet been executed. Returns 404 if the proposal does "
        "not exist."
    ),
)
# ID: d139934f-6d86-4e67-a9b0-41daba44dfa5
async def get_proposal_chain(
    proposal_id: str,
    session: AsyncSession = Depends(get_api_session),
    svc: ConsequenceLogService = Depends(get_consequence_log_service),
) -> dict:
    """Return the full governance chain for a proposal."""
    chain = await svc.get_chain_for_proposal(proposal_id, session)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal not found: {proposal_id}",
        )
    return chain


@router.get(
    "/{proposal_id}",
    response_model=ProposalResponse,
    summary="Fetch a single proposal",
    dependencies=[require_governor],
    description=(
        "Return a proposal by `proposal_id`. Returns 404 if no proposal "
        "exists with that id."
    ),
)
# ID: f99b7ebf-5664-4642-9ac0-500b2fa56216
async def get_proposal(
    proposal_id: str,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return a single proposal by id."""
    service = ProposalService(session)
    proposal = await service.get(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Proposal not found: {proposal_id}",
        )
    return proposal.to_dict()


@router.post(
    "/{proposal_id}/approve",
    summary="Approve a pending proposal",
    dependencies=[require_governor],
    description=(
        "Approve a proposal awaiting governance review. `approval_authority` "
        "is non-omittable per URS NFR.5 and validated against the "
        "`proposal_approval_authority` closed set inside ProposalStateManager. "
        "Returns 404 if the proposal doesn't exist; 400 if the authority is "
        "outside the closed vocabulary or the proposal is in a non-approvable state."
    ),
)
# ID: 499722f9-8c4c-4d04-99b2-aed56329c592
async def approve_proposal(
    proposal_id: str,
    payload: ApproveRequest,
    user: dict = require_governor,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Approve a pending proposal.

    `approval_authority` is non-omittable per URS NFR.5 and validated
    against the proposal_approval_authority closed set inside
    ProposalStateManager.approve. `approved_by` is derived from the
    request context (trusted-localhost in OSS mode).
    """
    approved_by = user.get("email") or user.get("sub", "unknown")
    service = ProposalService(session)
    try:
        await service.approve(
            proposal_id,
            approved_by=approved_by,
            approval_authority=payload.approval_authority,
        )
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "status": ProposalStatus.APPROVED.value,
        "approved_by": approved_by,
        "approval_authority": payload.approval_authority,
    }


@router.post(
    "/{proposal_id}/reject",
    summary="Reject a proposal",
    dependencies=[require_governor],
    description=(
        "Reject a proposal with a reason. Per ADR-010 §7a, rejection is "
        "symmetric with `mark_failed`: any findings parked at "
        "`deferred_to_proposal` are revived (flipped to `awaiting_reaudit` "
        "per ADR-045) so the audit sensor re-adjudicates them. Response "
        "includes `revived_count` for the operator. Returns 404 if the "
        "proposal doesn't exist."
    ),
)
# ID: 5c3091dd-b88f-4ebf-8de5-285f24f90ef8
async def reject_proposal(
    proposal_id: str,
    payload: RejectRequest,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Reject a proposal with a reason.

    Per ADR-010 §7a, rejection is symmetric with mark_failed: findings
    parked at deferred_to_proposal must be revived so they reach the
    audit sensor for re-adjudication, otherwise they strand. Revival
    flips them to awaiting_reaudit per ADR-045; the AuditViolationSensor
    decides on the next cycle whether to release to 'open' or resolve.
    """
    service = ProposalService(session)
    try:
        revived_count = await service.reject(proposal_id, reason=payload.reason)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "status": ProposalStatus.REJECTED.value,
        "reason": payload.reason,
        "revived_count": revived_count,
    }


@router.post(
    "/{proposal_id}/execute",
    summary="Execute an approved proposal",
    dependencies=[require_governor],
    description=(
        "Execute an approved proposal as a governor-direct override. "
        'Defaults to dry-run; pass `{"write": true}` to apply changes. '
        "The proposal must be in approved status; ProposalExecutor manages "
        "its own session lifecycle."
    ),
)
# ID: aaa55146-21cc-4945-bb2e-d0e083dfd6ff
async def execute_proposal(
    proposal_id: str,
    payload: ExecuteRequest,
    request: Request,
) -> dict:
    """Execute an approved proposal (governor-direct override).

    Defaults to dry-run; pass `{"write": true}` to apply changes.
    ProposalExecutor manages its own session via service_registry, so
    no get_api_session dependency is required here. Executor invocation
    routes through the will.governance.proposal_runner facade (#771).
    """
    core_context: CoreContext = request.app.state.core_context
    return await execute_proposal_direct(
        core_context,
        proposal_id=proposal_id,
        claimer=API_CLAIMER_UUID,
        write=payload.write,
    )

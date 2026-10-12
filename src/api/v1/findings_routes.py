# src/api/v1/findings_routes.py

"""
Findings API endpoints — blackboard entry query surface.

CONSTITUTIONAL:
- Session access goes through api.dependencies.get_api_session only.
- ConsequenceLogService is injected from api.dependencies (ConsequenceLogDep);
  no Body import here (architecture.api.no_body_bypass).
- Closing a finding delegated to a human is a governor act: the server stamps
  ``resolved_by`` and ``resolution_authority`` from the verified caller
  (ADR-132 D10.4); the request supplies only the reason.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    ConsequenceLogDep,
    FindingResolverDep,
    get_api_session,
    require_governor,
)
from api.v1.schemas import GovernanceChainResponse


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/findings")


# ID: 8b80089d-9f1d-432d-bcb4-b46b59a04b97
class ResolveFindingRequest(BaseModel):
    """Body for POST /findings/{entry_id}/resolve: the reason only."""

    reason: str = Field(min_length=1)


@router.get(
    "/{entry_id}/chain",
    response_model=GovernanceChainResponse,
    summary="Governance chain for a finding",
    dependencies=[require_governor],
    description=(
        "Reverse lookup: given a blackboard finding entry ID, locate the proposal "
        "it was deferred to and return the full governance chain — the proposal, "
        "all linked findings, and the execution consequence. Returns 404 if the "
        "entry does not exist or has not been linked to a proposal."
    ),
)
# ID: 3f71f3a8-efad-4fbe-bb0b-4572693b1a91
async def get_finding_chain(
    entry_id: str,
    svc: ConsequenceLogDep,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Return the governance chain for the proposal a finding was deferred to."""
    proposal_id = await svc.get_finding_proposal_link(entry_id, session)
    if proposal_id is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Finding {entry_id!r} not found or has no linked proposal. "
                "Only findings in 'deferred_to_proposal' or 'resolved' status "
                "carry a proposal link."
            ),
        )
    chain = await svc.get_chain_for_proposal(proposal_id, session)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"Linked proposal {proposal_id!r} not found.",
        )
    return chain


@router.post(
    "/{entry_id}/resolve",
    summary="Close a finding delegated to the governor",
    dependencies=[require_governor],
    description=(
        "Close a finding the audit sensor delegated to a human ('indeterminate', "
        "or 'open' with resolution_mechanism 'human'). Only the governor, on "
        "CORE's Unix socket, may call it (403 otherwise). The server stamps "
        "`resolved_by` (the governor's OS account) and `resolution_authority` "
        "(`principal.governor`); the body carries only the reason. Returns 404 "
        "if the entry does not exist or is not delegated to a human."
    ),
)
# ID: eae3eeb8-597b-4b1e-83a9-b3e65b5d052e
async def resolve_finding(
    entry_id: str,
    payload: ResolveFindingRequest,
    resolve: FindingResolverDep,
    user: dict = require_governor,
) -> dict:
    """Close a human-delegated finding, stamped from the verified caller."""
    updated = await resolve(
        entry_id=entry_id,
        reason=payload.reason,
        resolved_by=user["sub"],
        resolution_authority=user["principal"],
    )
    if updated == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Finding {entry_id!r} is not delegated to a human ('indeterminate', "
                "or 'open' with resolution_mechanism 'human') or does not exist."
            ),
        )
    return {
        "ok": True,
        "entry_id": entry_id,
        "status": "resolved",
        "resolved_by": user["sub"],
        "resolution_authority": user["principal"],
    }

# src/api/v1/findings_routes.py

"""
Findings API endpoints — blackboard entry query surface.

CONSTITUTIONAL:
- Session access goes through api.dependencies.get_api_session only.
- ConsequenceLogService is the sole Body import; this is the composition-root
  pattern (api.no_body_bypass [r] reporting, not blocking).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_api_session,
    get_consequence_log_service,
    require_governor,
)
from api.v1.schemas import GovernanceChainResponse
from body.services.consequence_log_service import ConsequenceLogService


ROUTER_EXPOSURE = "user-facing"
router = APIRouter(prefix="/findings")


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
    session: AsyncSession = Depends(get_api_session),
    svc: ConsequenceLogService = Depends(get_consequence_log_service),
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

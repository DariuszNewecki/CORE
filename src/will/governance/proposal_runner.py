# src/will/governance/proposal_runner.py

"""
Proposal runner facade — Will-layer entry point for the /proposals API
(ADR-049 D1 architectural-debt closure; #771).

The API layer must not construct domain objects or reach into
`will.autonomy.*` directly — that is the "API → Will use-case layer"
ADR-049 D1 recorded as architectural debt (the advisory rule
`architecture.api.must_route_through_will`). This module is the sanctioned
bridge for the /proposals surface, mirroring the `fix_runner` /
`sync_runner` facades the /fix and /sync surfaces already use.

Two governor-direct operations previously done inline in
`api/v1/proposals_routes.py`:

* `create_and_score_proposal` — build a Proposal from a goal + action
  sequence, compute its risk, and (when write=True) persist via
  ProposalService. Governor-initiated ad-hoc creation — a distinct code
  path from `violation_remediator_proposal.create_proposal`, which is
  autonomous findings-driven remediation.
* `execute_proposal_direct` — governor-direct override execution via
  ProposalExecutor (manages its own session lifecycle).

The remaining /proposals endpoints (list/get/approve/reject/chain) already
delegate to `ProposalService` / `ConsequenceLogService` facades and need no
runner wrapper — they carry no domain construction.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.context import CoreContext
from shared.logger import getLogger


__all__ = [
    "create_and_score_proposal",
    "execute_proposal_direct",
]


logger = getLogger(__name__)


# ID: a734e901-6214-4914-ade1-38d32d39dacc
async def create_and_score_proposal(
    session: Any,
    *,
    goal: str,
    actions: list[dict[str, Any]],
    files: list[str],
    created_by: str,
    write: bool,
) -> dict[str, Any]:
    """Build, risk-score, and (optionally) persist a proposal.

    Domain construction (ProposalAction/Proposal/ProposalScope +
    compute_risk) lives here, not in the route. With write=False the
    proposal is constructed and scored in-memory but not written; with
    write=True it is persisted via ProposalService and committed.

    Returns the API-shaped dict the route surfaces verbatim:
    {"ok", "persisted", "proposal"}.
    """
    from will.autonomy.proposal import Proposal, ProposalAction, ProposalScope
    from will.autonomy.proposal_service import ProposalService

    proposal_actions = [
        ProposalAction(
            action_id=a.get("action_id"),
            flow_id=a.get("flow_id"),
            parameters=a.get("parameters", {}),
            order=a.get("order", i),
        )
        for i, a in enumerate(actions)
    ]
    proposal = Proposal(
        goal=goal,
        actions=proposal_actions,
        scope=ProposalScope(files=files),
        created_by=created_by,
    )
    proposal.compute_risk()

    if write:
        service = ProposalService(session)
        await service.create(proposal)
        await session.commit()

    return {
        "ok": True,
        "persisted": write,
        "proposal": proposal.to_dict(),
    }


# ID: 9e46539b-f013-4e11-933a-29a4ffeefd0f
async def execute_proposal_direct(
    context: CoreContext,
    *,
    proposal_id: str,
    claimer: UUID,
    write: bool,
) -> dict[str, Any]:
    """Execute an approved proposal as a governor-direct override.

    ProposalExecutor manages its own session lifecycle via
    service_registry, so no caller-supplied session is threaded here.
    Returns ProposalExecutor.execute's result dict verbatim.
    """
    from will.autonomy.proposal_executor import ProposalExecutor

    executor = ProposalExecutor(context)
    return await executor.execute(proposal_id, claimer, write=write)

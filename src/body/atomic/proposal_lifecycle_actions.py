# src/body/atomic/proposal_lifecycle_actions.py

"""
Proposal lifecycle atomic actions. Per ADR-017, state mutations on
core.autonomous_proposals belong in governed atomic actions. This file
currently contains claim.proposal; future complete.proposal /
fail.proposal / approve.proposal / reject.proposal actions will live
here when the case for migrating them accumulates.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from body.atomic.registry import ActionCategory, register_action
from body.services.service_registry import service_registry
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="claim.proposal",
    description=(
        "Atomically claim an approved proposal for execution under worker attribution"
    ),
    category=ActionCategory.STATE,
    policies=["rules/will/autonomy"],
    impact_level="safe",
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id="claim.proposal",
    intent="Atomically claim an approved proposal under worker attribution",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 7d2f4a18-9c3e-4b50-8e21-3f6a5b8d1c04
async def action_claim_proposal(
    core_context: CoreContext,
    write: bool = False,
    proposal_id: str | None = None,
    claimed_by: UUID | None = None,
) -> ActionResult:
    """Atomically claim an approved proposal for execution.

    UPDATEs core.autonomous_proposals setting status='executing',
    execution_started_at=NOW(), claimed_by=$claimed_by with a WHERE that
    requires status='approved'. Single-claim atomicity rides on the
    autonomous_proposals_executing_once partial unique index (ADR-017 D1).

    write=False: read-only existence/status check; returns would_claim=True
    on a row that could be claimed.
    write=True:  the UPDATE; rowcount==0 means lost-the-race or not-approved.
    """
    start_time = time.time()

    if not proposal_id:
        return ActionResult(
            action_id="claim.proposal",
            ok=False,
            data={"error": "proposal_id is required"},
            duration_sec=time.time() - start_time,
        )
    if claimed_by is None:
        return ActionResult(
            action_id="claim.proposal",
            ok=False,
            data={"error": "claimed_by is required"},
            duration_sec=time.time() - start_time,
        )

    try:
        async with service_registry.session() as session:
            from shared.infrastructure.database.models.autonomous_proposals import (
                AutonomousProposal,
            )

            if not write:
                check_stmt = select(AutonomousProposal.proposal_id).where(
                    AutonomousProposal.proposal_id == proposal_id,
                    AutonomousProposal.status == ProposalStatus.APPROVED.value,
                )
                check_result = await session.execute(check_stmt)
                if check_result.scalar_one_or_none() is None:
                    return ActionResult(
                        action_id="claim.proposal",
                        ok=False,
                        data={
                            "error": "proposal not found or not approved",
                            "proposal_id": proposal_id,
                        },
                        duration_sec=time.time() - start_time,
                    )
                return ActionResult(
                    action_id="claim.proposal",
                    ok=True,
                    data={
                        "proposal_id": proposal_id,
                        "claimed_by": str(claimed_by),
                        "would_claim": True,
                        "dry_run": True,
                    },
                    duration_sec=time.time() - start_time,
                )

            stmt = (
                update(AutonomousProposal)
                .where(
                    AutonomousProposal.proposal_id == proposal_id,
                    AutonomousProposal.status == ProposalStatus.APPROVED.value,
                )
                .values(
                    status=ProposalStatus.EXECUTING.value,
                    execution_started_at=datetime.now(UTC),
                    claimed_by=claimed_by,
                )
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                await session.rollback()
                logger.warning(
                    "claim.proposal: %s already claimed or not approved",
                    proposal_id,
                )
                return ActionResult(
                    action_id="claim.proposal",
                    ok=False,
                    data={
                        "error": "proposal already claimed or not approved",
                        "proposal_id": proposal_id,
                    },
                    duration_sec=time.time() - start_time,
                )
            await session.commit()
            logger.info("claim.proposal: claimed %s by %s", proposal_id, claimed_by)
            return ActionResult(
                action_id="claim.proposal",
                ok=True,
                data={
                    "proposal_id": proposal_id,
                    "claimed_by": str(claimed_by),
                    "claimed": True,
                },
                duration_sec=time.time() - start_time,
            )
    except Exception as e:
        logger.exception("claim.proposal: failed for %s", proposal_id)
        return ActionResult(
            action_id="claim.proposal",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
                "proposal_id": proposal_id,
            },
            duration_sec=time.time() - start_time,
        )

# src/will/workers/proposal_consumer_revival.py
"""
§7a revival contract for ProposalConsumerWorker.

When a proposal terminates non-successfully (executor returned ok=False, or
the executor raised before completing), the findings that were deferred
under it must be revived back to 'open' status so the next remediation
cycle can re-claim them. This module owns that contract.

Two operations:

- revive_and_report: call BlackboardService.revive_findings_for_failed_proposal
  (UPDATE-only — clears claimed_by/claimed_at/resolved_at, flips status to
  'open' for any finding whose payload.proposal_id matches and is still
  parked at 'deferred_to_proposal'), then post a
  proposal.failure.revival::<id> report when one or more findings were
  revived. The post flows through the passed-in Worker so the report
  carries Worker attribution per ADR-011.
- mark_proposal_failed: open a dedicated session, instantiate
  ProposalStateManager, transition the proposal row to 'failed'. Used by
  the worker's outer-exception branch where ProposalExecutor never reached
  its own mark_failed because it raised before completion.

Fail-soft throughout: revival or post errors are logged but never
propagated; the worker's run-loop accounting decisions (failed += 1) must
not be reversed by a hiccup in the revival path.

LAYER: will/workers — internal collaborator of ProposalConsumerWorker.
Uses body service registry for blackboard + session access; no direct
database imports.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: f8e63aaf-638c-49fe-88da-b6679eb67624
async def revive_and_report(
    worker: Worker,
    proposal_id: str,
    reason: str,
) -> None:
    """
    Execute the §7a revival contract for a non-successfully-terminated
    proposal: revive deferred findings via BlackboardService, then post a
    revival report through the Worker for attribution.

    Implements CORE-Finding.md §7a steps 1-3:
      1+2 (state transition) — delegated to
          BlackboardService.revive_findings_for_failed_proposal
      3 (revival report)     — posted here via worker.post_report when one
                               or more findings were revived

    A zero-revival outcome is legitimate (the proposal had no deferred
    findings) and is logged silently; no report is posted in that case.
    """
    from body.services.service_registry import service_registry

    try:
        bb_service = await service_registry.get_blackboard_service()
        revival = await bb_service.revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason=reason,
        )
    except Exception as revive_err:
        logger.warning(
            "Revival query failed for proposal %s: %s",
            proposal_id,
            revive_err,
        )
        revival = None

    if not revival or revival.get("revived_count", 0) == 0:
        return

    try:
        await worker.post_report(
            subject=f"proposal.failure.revival::{proposal_id}",
            payload={
                "proposal_id": revival["proposal_id"],
                "failure_reason": revival["failure_reason"],
                "revived_count": revival["revived_count"],
                "revived_subjects": revival["revived_subjects"],
            },
        )
        logger.info(
            "ProposalConsumerWorker: posted revival report for "
            "proposal %s (%d findings revived)",
            proposal_id,
            revival["revived_count"],
        )
    except Exception as post_err:
        logger.warning(
            "Failed to post revival report for proposal %s: %s",
            proposal_id,
            post_err,
        )


# ID: b4208549-cde2-4707-9ad4-45de901366c9
async def mark_proposal_failed(proposal_id: str, reason: str) -> None:
    """
    Mark a proposal as 'failed' on the autonomous_proposals row.

    Used by the worker's outer-exception branch: if the executor raised
    before its internal mark_failed could run, the proposal is still
    APPROVED (or EXECUTING) and would strand without this step. Calling
    this prevents indefinite retry of a systematically broken proposal.

    Errors are logged and swallowed — the worker's primary concern is to
    proceed with revival regardless of whether the proposal-row UPDATE
    succeeded.
    """
    try:
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_state_manager import ProposalStateManager

        async with service_registry.session() as session:
            state_manager = ProposalStateManager(session)
            await state_manager.mark_failed(proposal_id, reason)
    except Exception as mark_err:
        logger.error(
            "ProposalConsumerWorker: failed to mark proposal '%s' as failed: %s",
            proposal_id,
            mark_err,
        )

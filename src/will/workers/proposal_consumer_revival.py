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

    This is the execution-failure path, so it passes the
    ``remediation_cap_n`` rail (ADR-104 D9 / #637): a finding that has now
    failed remediation that many times is abandoned (terminal Type-B) by the
    service instead of revived, and this worker posts the terminal
    ``blackboard.remediation_cap_reached::<entry_id>`` observation (D4 — not
    a silent instrument) per ``worker_only_inserts``. The governor-reject
    path (proposal_service.reject) does NOT pass the cap — a human decision
    is not a remediation failure and must not count toward auto-abandon.

    A zero-revival, zero-abandon outcome is legitimate (the proposal had no
    deferred findings) and is logged silently; nothing is posted then.
    """
    from body.services.service_registry import service_registry
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )

    cap_n = load_operational_config().blackboard.remediation_cap_n

    try:
        bb_service = await service_registry.get_blackboard_service()
        revival = await bb_service.revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason=reason,
            remediation_cap_n=cap_n,
        )
    except Exception as revive_err:
        logger.warning(
            "Revival query failed for proposal %s: %s",
            proposal_id,
            revive_err,
        )
        revival = None

    if not revival:
        return

    # ADR-104 D9 (#637): findings that reached the remediation-attempt cap
    # were abandoned terminally by the service. Post one terminal Type-B
    # observation per abandoned finding so the cap event is named and folds
    # into the F-19 `stuck` bucket. Posted here (not in the service) per
    # architecture.blackboard.worker_only_inserts.
    for entry_id in revival.get("abandoned_finding_ids", []):
        try:
            await worker.post_observation(
                subject=f"blackboard.remediation_cap_reached::{entry_id}",
                payload={
                    "entry_id": entry_id,
                    "proposal_id": revival["proposal_id"],
                    "failure_reason": revival["failure_reason"],
                    "reason": "remediation_cap_reached",
                    "remediation_cap_n": cap_n,
                },
                status="abandoned",
            )
            logger.warning(
                "ProposalConsumerWorker: finding %s abandoned at remediation "
                "cap (n=%d) for proposal %s",
                entry_id,
                cap_n,
                proposal_id,
            )
        except Exception as obs_err:
            logger.warning(
                "Failed to post remediation-cap observation for finding %s "
                "(proposal %s): %s",
                entry_id,
                proposal_id,
                obs_err,
            )

    if revival.get("revived_count", 0) == 0:
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

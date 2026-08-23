# src/will/workers/proposal_consumer_revival.py
"""
§7a revival contract for ProposalConsumerWorker.

When a proposal terminates non-successfully (executor returned ok=False, or
the executor raised before completing), the findings that were deferred
under it must be revived so the next remediation cycle — or, for the
assisted lane, the delegating agent — can pick the work back up. This
module owns that contract.

Three operations:

- revive_and_report: routes to the correct revival predicate by proposal
  lineage, then posts a proposal.failure.revival::<id> report when one or
  more findings were revived. The post flows through the passed-in Worker
  so the report carries Worker attribution per ADR-011.

  Three lineages (see will.autonomy.proposal_lineage), two distinct
  revival targets on EXECUTION failure — deliberately not one function per
  lineage, because ceremony deliberately shares the autonomous target here
  (it diverges only on explicit rejection — see proposal_service.reject):

  * Autonomous proposals (the ADR-035/ADR-010 mapped-remediation lane) AND
    ceremony proposals (ADR-154; constitutional_constraints
    ['proposal_origin'] == 'ceremony') whose approved candidate failed at
    EXECUTION time both use BlackboardService.revive_findings_for_failed_proposal
    — flips status to 'awaiting_reaudit' (ADR-045), passes the ADR-104 D9
    remediation-attempt cap so a finding that fails this many times is
    abandoned instead of revived forever. This is correct for ceremony
    findings specifically because they are born, and stay while deferred,
    resolution_mechanism='reaudit' — the same predicate
    revive_findings_for_failed_proposal already requires. A ceremony
    proposal's EXPLICIT REJECTION is a different lifecycle event with a
    different destination (indeterminate+human, via
    revive_ceremony_findings_for_rejected_proposal) — see
    proposal_service.reject, not this module.
  * Assisted-lane proposals (constitutional_constraints['assisted_lane'],
    ADR-109) whose approved candidate failed at EXECUTION time (distinct
    from an explicit governor rejection — see
    revive_delegated_findings_for_failed_proposal's own docstring):
    BlackboardService.revive_delegated_findings_for_failed_proposal —
    governor decision, 2026-08-23: lands back at 'indeterminate'+'human',
    preserving the delegation, clearing the stale agent work claim
    (payload.lane_claimed_by/lane_claimed_at), and NEVER entering the
    remediation-cap/circuit-breaker handling above — a human delegated
    this work; a failed attempt does not silently re-route it into the
    autonomous loop.

- mark_proposal_failed: open a dedicated session, instantiate
  ProposalStateManager, transition the proposal row to 'failed'. Used by
  the worker's outer-exception branch where ProposalExecutor never reached
  its own mark_failed because it raised before completion.
- release_executing_proposals: called in a finally block at the end of
  run() to release any proposals still in EXECUTING status owned by this
  worker (covers graceful-shutdown paths: SIGTERM → CancelledError,
  unhandled BaseException above the per-proposal try/except). Hard kills
  (SIGKILL) are not covered here; a periodic reaper is required for those.

Fail-soft throughout: revival or post errors are logged but never
propagated; the worker's run-loop accounting decisions (failed += 1) must
not be reversed by a hiccup in the revival path.

LAYER: will/workers — internal collaborator of ProposalConsumerWorker.
Uses body service registry for blackboard + session access; ProposalRepository
(will.autonomy, same layer) for the lineage read. No direct database imports.
"""

from __future__ import annotations

import uuid
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker
from will.autonomy.proposal_lineage import ProposalLineage, proposal_lineage


logger = getLogger(__name__)


async def _proposal_revival_lineage(proposal_id: str) -> ProposalLineage:
    """Classify *proposal_id*'s revival lineage via ``proposal_lineage()``
    (ADR-154 D3) — the explicit three-way read, not a bare truthy check on
    ``assisted_lane`` alone. Fail-closed to "autonomous" (the historical
    default) on any read error so a lookup hiccup degrades to existing
    behavior rather than silently routing an assisted-lane or ceremony
    proposal's findings into the wrong predicate, which would simply match
    zero rows and mask the failure differently."""
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository

    try:
        async with service_registry.session() as session:
            proposal = await ProposalRepository(session).get(proposal_id)
    except Exception as fetch_err:
        logger.warning(
            "Could not load proposal %s to determine revival lineage: %s — "
            "defaulting to the autonomous revival path",
            proposal_id,
            fetch_err,
        )
        return "autonomous"

    if proposal is None:
        return "autonomous"
    return proposal_lineage(proposal.constitutional_constraints)


async def _revive_autonomous(proposal_id: str, reason: str) -> dict[str, Any] | None:
    """The pre-existing autonomous revival call, unchanged: passes the
    ADR-104 D9 remediation-attempt cap."""
    from body.services.service_registry import service_registry
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )

    cap_n = load_operational_config().blackboard.remediation_cap_n

    try:
        bb_service = await service_registry.get_blackboard_service()
        return await bb_service.revive_findings_for_failed_proposal(
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
        return None


async def _revive_assisted_lane(proposal_id: str, reason: str) -> dict[str, Any] | None:
    """Assisted-lane execution-failure revival — no remediation cap; the
    delegation is preserved regardless of how many times it has failed
    (governor decision, 2026-08-23)."""
    from body.services.service_registry import service_registry

    try:
        bb_service = await service_registry.get_blackboard_service()
        return await bb_service.revive_delegated_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason=reason,
        )
    except Exception as revive_err:
        logger.warning(
            "Assisted-lane revival query failed for proposal %s: %s",
            proposal_id,
            revive_err,
        )
        return None


# ID: f8e63aaf-638c-49fe-88da-b6679eb67624
async def revive_and_report(
    worker: Worker,
    proposal_id: str,
    reason: str,
) -> None:
    """
    Execute the §7a revival contract for a non-successfully-terminated
    proposal: revive deferred findings via the lineage-appropriate
    BlackboardService predicate, then post a revival report through the
    Worker for attribution.

    Implements CORE-Finding.md §7a steps 1-3:
      1+2 (state transition) — delegated to
          BlackboardService.revive_findings_for_failed_proposal (autonomous
          AND ceremony — see module docstring and ADR-154 D3: a ceremony
          proposal's EXECUTION failure follows the same ADR-038 circuit-
          breaker path as a plain autonomous proposal, because ceremony
          findings stay resolution_mechanism='reaudit' while deferred) or
          .revive_delegated_findings_for_failed_proposal (assisted-lane) —
          see module docstring for the lineage split.
      3 (revival report)     — posted here via worker.post_report when one
                               or more findings were revived, using the
                               same proposal.failure.revival::<id> shape
                               regardless of lineage (all revival dicts
                               share the same key shape by design).

    The ADR-104 D9 remediation-attempt cap (a finding that has now failed
    remediation that many times is abandoned (terminal Type-B) instead of
    revived, with a terminal
    ``blackboard.remediation_cap_reached::<finding_subject>`` observation
    per ``worker_only_inserts``) applies to the autonomous AND ceremony
    lineages alike (both revive via the same capped call). The
    governor-reject path (proposal_service.reject) never passes it — a
    human decision is not a remediation failure — and neither does
    assisted-lane execution failure, for the same reason (governor
    decision, 2026-08-23): a human delegated the work; the delegation does
    not expire because one attempt failed to execute.

    A zero-revival, zero-abandon outcome is legitimate (the proposal had no
    deferred findings) and is logged silently; nothing is posted then.
    """
    lineage = await _proposal_revival_lineage(proposal_id)
    if lineage == "assisted_lane":
        revival = await _revive_assisted_lane(proposal_id, reason)
    else:
        # "ceremony" and "autonomous" share the same execution-failure
        # revival target (ADR-038) — see the docstring above for why.
        revival = await _revive_autonomous(proposal_id, reason)

    if not revival:
        return

    # ADR-104 D9 (#637): findings that reached the remediation-attempt cap
    # were abandoned terminally by the service. Post one terminal Type-B
    # observation per abandoned finding so the cap event is named and folds
    # into the F-19 `stuck` bucket. Posted here (not in the service) per
    # architecture.blackboard.worker_only_inserts.
    #
    # Subject uses the original finding's subject (stable per violation class),
    # not entry_id (UUID), so the same violation does not generate a new F-19
    # subject each time it cycles through the cap. abandoned_finding_ids is
    # only ever non-empty on the autonomous path (assisted-lane revival never
    # abandons), so cap_n is only actually read when the loop body below
    # runs — but it must still resolve, since bare cap_n is no longer in this
    # function's scope after the lineage split.
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )

    cap_n = load_operational_config().blackboard.remediation_cap_n

    abandoned_ids = revival.get("abandoned_finding_ids", [])
    abandoned_subjects = revival.get("abandoned_subjects", [])
    for entry_id, finding_subject in zip(abandoned_ids, abandoned_subjects):
        try:
            await worker.post_observation(
                subject=f"blackboard.remediation_cap_reached::{finding_subject}",
                payload={
                    "entry_id": entry_id,
                    "finding_subject": finding_subject,
                    "proposal_id": revival["proposal_id"],
                    "failure_reason": revival["failure_reason"],
                    "reason": "remediation_cap_reached",
                    "remediation_cap_n": cap_n,
                },
                status="abandoned",
            )
            logger.warning(
                "ProposalConsumerWorker: finding %s (%s) abandoned at remediation "
                "cap (n=%d) for proposal %s",
                entry_id,
                finding_subject,
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


# ID: fd8678bd-94fd-439e-8bd3-d1f1ede79850
async def release_executing_proposals(
    worker: Worker,
    worker_uuid: uuid.UUID,
) -> int:
    """
    Release any proposals stuck in EXECUTING status claimed by this worker.

    Called in a finally block in run() to handle graceful-shutdown paths:
    SIGTERM arrives as CancelledError in asyncio — the per-proposal
    try/except catches only Exception, so CancelledError (and any other
    BaseException) skips mark_proposal_failed for the in-flight proposal.
    This function finds and repairs that gap.

    For each stuck proposal, applies the same failure+revival path as the
    ordinary exception branch: mark_failed transitions the row out of
    EXECUTING, revive_and_report unparks deferred findings. Fully fail-soft.

    Returns the count of proposals released (0 on normal exit).
    """
    from sqlalchemy import select

    from body.services.service_registry import service_registry
    from shared.infrastructure.database.models.autonomous_proposals import (
        AutonomousProposal,
    )
    from will.autonomy.proposal import ProposalStatus

    released = 0
    try:
        async with service_registry.session() as session:
            stmt = (
                select(AutonomousProposal.proposal_id)
                .where(AutonomousProposal.status == ProposalStatus.EXECUTING.value)
                .where(AutonomousProposal.claimed_by == worker_uuid)
            )
            result = await session.execute(stmt)
            stuck_ids = [str(row[0]) for row in result.fetchall()]
    except Exception as query_err:
        logger.error(
            "ProposalConsumerWorker: could not query stuck proposals for worker %s: %s",
            worker_uuid,
            query_err,
        )
        return 0

    reason = "worker terminated during execution (finally-block release)"
    for proposal_id in stuck_ids:
        logger.warning(
            "ProposalConsumerWorker: releasing stuck proposal '%s' "
            "(was EXECUTING, claimed_by=%s)",
            proposal_id,
            worker_uuid,
        )
        await mark_proposal_failed(proposal_id, reason)
        await revive_and_report(worker, proposal_id, reason)
        released += 1

    return released

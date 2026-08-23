# src/body/services/proposal_submission_service.py
"""
Atomic proposal-submission service (ADR-109, ADR-154 D3b).

Fixes a live defect found during D2 review: ``LaneService.propose_validated_diff``
previously created the Proposal in one session and deferred its finding in a
*separate*, independently-committing session. The old ``ProposalRepository
.create()`` call chain only ``session.add()`` + ``session.flush()``\\ ed —
commit was left to a caller that never called it. Verified empirically:
flush + session.close() with no intervening commit leaves zero durable rows.
The finding-deferral call, in its own session using ``session.begin()``, DID
commit — so a finding could be durably stamped ``deferred_to_proposal``
against a ``proposal_id`` that was never actually persisted. Phantom-proposal
split state, live in production before this fix.

This module is also the first concrete instance of ADR-154 D3b's atomicity
requirement: "a Body-owned service performs candidate persistence, proposal
creation, and finding deferral within one database transaction." It accepts
``finding_ids`` as a set (not assumed singular) so the same transactional
shape is structurally ready to be reused once ceremony (Slice B) needs it —
but this module currently implements only the assisted-lane eligibility
predicate (``status='indeterminate' AND resolution_mechanism='human'``); a
ceremony-shaped predicate (``open``/``claimed``) is future work, not built
speculatively here.

Layering (``architecture.layers.no_body_to_will``, no excludes, applies to
every file in this directory): this module accepts an already-mapped
``AutonomousProposal`` — the persistence model in
``shared.infrastructure.database.models.autonomous_proposals`` — never the
Will-layer ``Proposal`` domain dataclass. The Will→persistence-model mapping
(``ProposalMapper.to_db_model``, already a stateless, no-DB-access utility)
runs in the caller (``LaneService``), which owns constructing/mapping the
governed proposal representation; this module owns ``session.add``/
``flush``, the eligibility recheck, every finding deferral, and the single
commit — the Body-owned half of D3b's atomicity requirement, with no
upward-borrowed Will import.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.database.models.autonomous_proposals import (
        AutonomousProposal,
    )

logger = getLogger(__name__)


# ID: 5c6910d8-6d13-403f-9633-1a9b3e0e6332
class ProposalSubmissionError(Exception):
    """Raised when a proposal cannot be atomically submitted with its
    finding deferrals.

    One or more source findings were no longer eligible (already worked,
    resolved, or claimed elsewhere) by the time the transaction ran. The
    whole submission — proposal included — is rolled back; nothing is
    persisted.
    """


# ID: 2ad29754-9984-49c2-8536-84877f7a0884
async def submit_assisted_lane_proposal(
    proposal_model: AutonomousProposal,
    finding_ids: list[str],
) -> str:
    """Atomically persist *proposal_model* and defer every id in
    *finding_ids* to it.

    *proposal_model* is an already-constructed, unsaved
    ``AutonomousProposal`` instance — typically via ``ProposalMapper
    .to_db_model(proposal, AutonomousProposal)`` in the caller — with its
    ``proposal_id`` already set (the Will-layer ``Proposal`` dataclass
    generates it client-side). This function never constructs or
    interprets the governed proposal representation itself; it only
    persists what it is handed and defers findings to it.

    Single transaction (ADR-154 D3b): opens one session, adds the proposal
    model and defers every finding inside it, commits once. Re-verifies
    eligibility of every finding inside that same transaction via one
    ``UPDATE ... WHERE ... RETURNING`` — the compare-and-swap shape that
    checks and mutates atomically, so there is no separate check-then-act
    race window between the eligibility recheck and the deferral itself.
    The predicate matches the assisted-lane governor-inbox shape
    (``status='indeterminate' AND resolution_mechanism='human'``) — the
    same one ``LaneService`` already gates the lane queue on.

    If any finding is no longer eligible (an intervening claim, resolution,
    or another proposal since the caller's own pre-check), the entire
    transaction — proposal included — rolls back and no partial state is
    left: no proposal row, no finding transitioned.

    Returns the proposal id, but only after a successful commit.

    Raises:
        ProposalSubmissionError: *finding_ids* was empty, or fewer findings
            were deferred than requested (the submission did not proceed).
    """
    if not finding_ids:
        raise ProposalSubmissionError(
            "submit_assisted_lane_proposal requires at least one finding_id"
        )

    async with service_registry.session() as session:
        async with session.begin():
            session.add(proposal_model)
            await session.flush()
            proposal_id = str(proposal_model.proposal_id)

            result = await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = 'deferred_to_proposal',
                        resolved_at = now(),
                        updated_at = now(),
                        payload = payload || jsonb_build_object(
                            'proposal_id', cast(:proposal_id as text)
                        )
                    WHERE id = ANY(cast(:ids as uuid[]))
                      AND status = 'indeterminate'
                      AND resolution_mechanism = 'human'
                    RETURNING id
                    """
                ),
                {"proposal_id": proposal_id, "ids": finding_ids},
            )
            deferred_ids = {str(row[0]) for row in result.fetchall()}

            if len(deferred_ids) != len(finding_ids):
                stale = sorted(set(finding_ids) - deferred_ids)
                raise ProposalSubmissionError(
                    f"{len(stale)}/{len(finding_ids)} finding(s) no longer "
                    "eligible for deferral (not a live delegated lane item "
                    f"at submission time): {stale}. Proposal not created — "
                    "submission is all-or-nothing (ADR-154 D3b)."
                )

        # session.begin() committed on clean exit — proposal_id is now durable.
        logger.info(
            "proposal_submission: proposal %s committed with %d finding(s) "
            "deferred atomically",
            proposal_id,
            len(deferred_ids),
        )
        return proposal_id


# ID: d5c6b1b9-a6d9-48db-aa6d-5f4260686553
async def submit_ceremony_proposal(
    proposal_model: AutonomousProposal,
    finding_ids: list[str],
    expected_worker_uuid: uuid.UUID,
    expected_rule_ids: list[str],
) -> str:
    """Atomically persist *proposal_model* and defer every id in
    *finding_ids* to it — the ceremony-lane analogue of
    ``submit_assisted_lane_proposal`` (ADR-154 D3/D3b).

    Same single-transaction shape (add + flush + one compare-and-swap
    UPDATE...RETURNING + commit once), a genuinely different eligibility
    predicate: ceremony findings live at ``status='claimed'`` with a real
    worker ``claimed_by`` UUID (``ViolationExecutorWorker``/
    ``RemediatorWorker`` claim machinery), never
    ``indeterminate+human`` — the assisted-lane governor-inbox shape does
    not apply here. Two checks the assisted-lane predicate has no
    equivalent for, both required by ADR-154 D5's eligibility guard:

    - ``claimed_by`` must equal *expected_worker_uuid* — not merely *some*
      worker. A finding reassigned to a different worker between claim and
      submission (e.g. released and re-claimed after this worker stalled)
      is no longer this submission's to defer; deferring it anyway would
      silently steal another worker's in-progress claim.
    - the source findings' ``payload->>'rule'`` set must exactly equal
      *expected_rule_ids* — the candidate's own validated rule set (see
      ``validated_candidate_service.build_validated_candidate``'s matching
      check). A candidate must be built from exactly the findings it
      claims to fix, not a superset or subset of them.

    ``resolution_mechanism`` is deliberately NOT touched by the deferral
    UPDATE — ceremony findings are born (ADR-091 D2's invariant) and stay
    ``'reaudit'`` while deferred, so an execution failure later reaches the
    existing generic ``revive_findings_for_failed_proposal`` (ADR-038
    circuit-breaker) path exactly as an ordinary autonomous proposal would.
    Only an explicit governor rejection moves a ceremony finding to
    ``indeterminate+human``, via the separate
    ``revive_ceremony_findings_for_rejected_proposal`` operation — a
    different lifecycle event with a different destination, deliberately
    not conflated with this deferral.

    If any row is missing, not ``entry_type='finding'``, not
    ``status='claimed'``, claimed by a different worker, or the rule set
    does not match, the entire transaction — proposal included — rolls
    back and no partial state is left: no proposal row, no finding
    transitioned. The external-assisted submission path
    (``submit_assisted_lane_proposal``) is untouched by this function.

    Returns the proposal id, but only after a successful commit.

    Raises:
        ProposalSubmissionError: *finding_ids* was empty, fewer findings
            were deferred than requested (stale claim/status/ownership), or
            the deferred findings' rule set did not match
            *expected_rule_ids*.
    """
    if not finding_ids:
        raise ProposalSubmissionError(
            "submit_ceremony_proposal requires at least one finding_id"
        )

    async with service_registry.session() as session:
        async with session.begin():
            session.add(proposal_model)
            await session.flush()
            proposal_id = str(proposal_model.proposal_id)

            result = await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = 'deferred_to_proposal',
                        resolved_at = now(),
                        updated_at = now(),
                        payload = payload || jsonb_build_object(
                            'proposal_id', cast(:proposal_id as text)
                        )
                    WHERE id = ANY(cast(:ids as uuid[]))
                      AND entry_type = 'finding'
                      AND status = 'claimed'
                      AND claimed_by = cast(:expected_worker_uuid as uuid)
                    RETURNING id, payload->>'rule' AS rule
                    """
                ),
                {
                    "proposal_id": proposal_id,
                    "ids": finding_ids,
                    "expected_worker_uuid": str(expected_worker_uuid),
                },
            )
            rows = result.fetchall()
            deferred_ids = {str(row[0]) for row in rows}

            if len(deferred_ids) != len(finding_ids):
                stale = sorted(set(finding_ids) - deferred_ids)
                raise ProposalSubmissionError(
                    f"{len(stale)}/{len(finding_ids)} finding(s) no longer "
                    "eligible for ceremony deferral (not entry_type='finding' "
                    f"AND status='claimed' AND claimed_by={expected_worker_uuid} "
                    f"at submission time): {stale}. Proposal not created — "
                    "submission is all-or-nothing (ADR-154 D3b)."
                )

            actual_rules = {row[1] for row in rows if row[1]}
            expected_rules = set(expected_rule_ids)
            if actual_rules != expected_rules:
                raise ProposalSubmissionError(
                    f"Source findings' rule set {sorted(actual_rules)!r} does "
                    "not match the candidate's validated rule set "
                    f"{sorted(expected_rules)!r} — a candidate must be built "
                    "from exactly the findings it claims to fix. Proposal "
                    "not created."
                )

        # session.begin() committed on clean exit — proposal_id is now durable.
        logger.info(
            "proposal_submission: ceremony proposal %s committed with %d "
            "finding(s) deferred atomically (worker=%s)",
            proposal_id,
            len(deferred_ids),
            expected_worker_uuid,
        )
        return proposal_id

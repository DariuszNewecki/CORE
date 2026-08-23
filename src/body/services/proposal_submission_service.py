# src/body/services/proposal_submission_service.py
"""
Atomic proposal-submission service (ADR-109, ADR-154 D3b).

Fixes a live defect found during D2 review: ``LaneService.propose_validated_diff``
previously created the Proposal in one session and deferred its finding in a
*separate*, independently-committing session. ``ProposalRepository.create()``
only ``session.add()`` + ``session.flush()``\\ es — its own docstring says
commit is "left to the workflow orchestrator" — and nothing in the old
``ProposalService.open()`` call chain ever called it. Verified empirically:
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

Constitutional note: this module imports ``Proposal``/``ProposalRepository``
from ``will.autonomy`` — mechanically a ``architecture.layers.no_body_to_will``
reporting finding. ADR-154 D3b's own text requires "a Body-owned service
performs ... proposal creation" as one atomic unit with the deferral; the
alternative (Will owns the session, Body only runs the deferral SQL) would
split proposal-creation back out of the Body-owned unit the ADR calls for,
and re-implementing proposal persistence here (bypassing
``ProposalMapper``) would duplicate the mapping logic ``ProposalRepository``
already owns. This import is deliberate and ADR-authorized for this one
call, not a general precedent.
"""

from __future__ import annotations

from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.logger import getLogger
from will.autonomy.proposal import Proposal
from will.autonomy.proposal_repository import ProposalRepository


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
    proposal: Proposal,
    finding_ids: list[str],
) -> str:
    """Atomically persist *proposal* and defer every id in *finding_ids* to it.

    Single transaction (ADR-154 D3b): opens one session, creates the
    proposal and defers every finding inside it, commits once. Re-verifies
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
            repo = ProposalRepository(session)
            proposal_id = await repo.create(proposal)

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

# src/will/autonomy/producer_submission.py
"""One way in for a producer's change that is not born from a finding.

ADR-168 Amendment 2026-10-10 (A1-A7, R1-R5); producer build U7. A producer
(an assistant, the governor's own session, any agent) submits a patch it has
already validated in general mode (``assisted.validate_diff general=True``,
where CORE chose the checks). This service:

1. re-reads that validation run and binds the patch to it (the frozen
   candidate, ADR-154 D2) — the producer's word is never the verdict;
2. answers step 0 for the approver (``step_zero.build_step_zero_report``);
3. creates a PENDING proposal carrying the anchor, owner, producer and what
   it retires, approval always required.

It never approves, rejects or executes (A1). Finding-born work keeps its own
lanes; governed text is refused at validation (A5).
"""

from __future__ import annotations

from typing import Any

from body.services.service_registry import service_registry
from body.services.validated_candidate_service import build_validated_candidate
from shared.infrastructure.bootstrap_registry import bootstrap_registry
from shared.logger import getLogger
from will.autonomy.proposal import ProposalProvenance
from will.autonomy.proposal_factory import build_general_proposal
from will.autonomy.step_zero import build_step_zero_report


logger = getLogger(__name__)


# ID: e4113c0f-4ca7-42e6-9452-30dd1e102539
class ProducerSubmissionError(ValueError):
    """The submission is not acceptable; the message says why."""


# ID: 3977b189-240c-4196-a318-849774867dd1
async def submit_producer_change(
    *,
    patch: str,
    validation_run_id: str,
    goal: str,
    anchor_kind: str,
    anchor_refs: list[str],
    producer: str,
    retires: list[str] | None = None,
    created_by: str = "producer-submission",
) -> dict[str, Any]:
    """Create the pending proposal; returns its id, scope and step-0 report.

    Raises ``ProducerSubmissionError`` for a finding anchor (use the finding
    lane), malformed provenance or a malformed proposal, and lets
    ``CandidateConstructionError`` through for a validation run that does
    not bind this patch.
    """
    if anchor_kind == "finding":
        raise ProducerSubmissionError(
            "A finding-anchored change goes through the finding lane, which "
            "checks that the finding's rules clear."
        )
    provenance = ProposalProvenance(
        anchor_kind=anchor_kind,
        anchor_refs=list(anchor_refs),
        problem_owner="governor",
        producer=producer,
        retires=list(retires or []),
    )
    problems = provenance.problems()
    if problems:
        raise ProducerSubmissionError("; ".join(problems))

    candidate = await build_validated_candidate(
        finding_ids=[],
        rule_ids=[],
        patch=patch,
        validation_run_id=validation_run_id,
        general=True,
    )
    step_zero = await build_step_zero_report(
        patch=patch,
        retires=provenance.retires,
        repo_root=bootstrap_registry.get_repo_path(),
        cognitive_service=await service_registry.get_cognitive_service(),
    )
    proposal = build_general_proposal(
        candidate,
        goal=goal,
        created_by=created_by,
        provenance=provenance,
        step_zero=step_zero,
    )
    proposal.compute_risk()
    errors = proposal.check_submission()
    if errors:
        raise ProducerSubmissionError("; ".join(errors))

    from will.autonomy.proposal_service import ProposalService

    async with service_registry.session() as session:
        await ProposalService(session).create(proposal)
        await session.commit()

    logger.info(
        "producer_submission: proposal %s pending (producer=%s, anchor=%s)",
        proposal.proposal_id,
        producer,
        anchor_kind,
    )
    return {
        "proposal_id": proposal.proposal_id,
        "status": proposal.status.value,
        "approval_required": True,
        "scope_files": list(candidate.production_set),
        "step_zero": step_zero,
    }

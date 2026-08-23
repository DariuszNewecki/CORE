# src/will/autonomy/proposal_factory.py
"""
Shared human-gated DRAFT proposal construction (ADR-154 D1/D3).

The governed shape a `ValidatedRemediationCandidate` becomes is identical
regardless of which lane produced the candidate: `assisted.apply_diff`
carrying the exact validated patch, `approval_required=True` (ADR-109 D3 —
no lane may auto-approve an unmapped/judgment-dependent change), and the
candidate's own recorded evidence (validation_checks/results, finding_ids,
rule_ids, candidate_id, candidate_created_at) — never a caller-asserted
substitute. Extracted so the external-assisted lane (`LaneService
.propose_validated_diff`) and the ceremony lane (ADR-154 D3) cannot drift
into two different proposal shapes for what is constitutionally the same
form. Callers differ only in `goal`, `created_by`, and the lineage marker
threaded through `extra_constraints` (see `proposal_lineage.py`) — nothing
else about the proposal itself should differ by lane.
"""

from __future__ import annotations

from typing import Any

from shared.models.validated_remediation_candidate import (
    ValidatedRemediationCandidate,
)
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


# ID: 52201a7d-9380-484f-91b3-9afdec2c9c33
def build_assisted_lane_draft_proposal(
    candidate: ValidatedRemediationCandidate,
    *,
    goal: str,
    created_by: str,
    extra_constraints: dict[str, Any] | None = None,
) -> Proposal:
    """Build the ADR-109 human-gated DRAFT proposal for a validated candidate.

    *extra_constraints* is merged into `constitutional_constraints` after
    the candidate's own evidence fields — a lane's lineage marker (e.g.
    ``{"assisted_lane": True}`` or ``{"proposal_origin": "ceremony"}``)
    must never be able to shadow or override the candidate's recorded
    finding_ids/rules/candidate_id/patch_digest/validated_base_sha, so
    callers should not attempt to pass those keys in *extra_constraints*.
    """
    constraints: dict[str, Any] = {
        "finding_ids": candidate.finding_ids,
        "rules": candidate.rule_ids,
        "candidate_id": candidate.candidate_id,
        "patch_digest": candidate.patch_digest,
        "validated_base_sha": candidate.validated_base_sha,
        "candidate_created_at": candidate.created_at.isoformat(),
    }
    constraints.update(extra_constraints or {})

    return Proposal(
        goal=goal,
        actions=[
            ProposalAction(
                action_id="assisted.apply_diff",
                parameters={
                    "patch": candidate.patch,
                    "patch_digest": candidate.patch_digest,
                    "validated_base_sha": candidate.validated_base_sha,
                    "write": True,
                },
                order=0,
            )
        ],
        scope=ProposalScope(files=list(candidate.production_set)),
        status=ProposalStatus.DRAFT,
        created_by=created_by,
        validation_checks=candidate.validation_checks,
        validation_results=candidate.validation_results,
        # ADR-109 D3 — mandatory for every lane this factory serves; neither
        # lane qualifies for Lane 1's deterministic-mapping safe_auto_approval.
        approval_required=True,
        constitutional_constraints=constraints,
    )

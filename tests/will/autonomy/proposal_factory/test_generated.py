from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from will.autonomy.proposal_factory import build_assisted_lane_proposal


# ID: fca59f66-c097-4a0b-8d95-88b84108797c
def test_build_assisted_lane_proposal():
    candidate = MagicMock()
    candidate.finding_ids = ["finding-1"]
    candidate.rule_ids = ["rule-a"]
    candidate.candidate_id = "cand-123"
    candidate.patch_digest = "sha256:abc"
    candidate.validated_base_sha = "deadbeef"
    candidate.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    candidate.patch = "--- a\n+++ b\n"
    candidate.production_set = ["src/foo.py"]
    candidate.validation_checks = ["lint"]
    candidate.validation_results = {"lint": "pass"}

    proposal = build_assisted_lane_proposal(
        candidate,
        goal="fix the thing",
        created_by="tester",
        producer="agent-x",
        extra_constraints={"assisted_lane": True},
    )

    assert proposal.goal == "fix the thing"
    assert proposal.created_by == "tester"
    assert proposal.approval_required is True

    constraints = proposal.constitutional_constraints
    assert constraints["finding_ids"] == ["finding-1"]
    assert constraints["rules"] == ["rule-a"]
    assert constraints["candidate_id"] == "cand-123"
    assert constraints["patch_digest"] == "sha256:abc"
    assert constraints["validated_base_sha"] == "deadbeef"
    assert constraints["candidate_created_at"] == candidate.created_at.isoformat()
    assert constraints["assisted_lane"] is True

    assert len(proposal.actions) == 1
    action = proposal.actions[0]
    assert action.action_id == "assisted.apply_diff"
    assert action.parameters["patch"] == candidate.patch
    assert action.parameters["patch_digest"] == "sha256:abc"
    assert action.parameters["validated_base_sha"] == "deadbeef"
    assert action.parameters["write"] is True

    assert list(proposal.scope.files) == ["src/foo.py"]
    assert proposal.provenance.anchor_kind == "finding"
    assert list(proposal.provenance.anchor_refs) == ["finding-1"]
    assert proposal.provenance.problem_owner == "core"
    assert proposal.provenance.producer == "agent-x"

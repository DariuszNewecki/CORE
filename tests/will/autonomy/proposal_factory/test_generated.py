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



from will.autonomy.proposal_factory import build_general_proposal


# ID: b9e8ae9d-5c5e-44f4-b64e-11bc0d4cfb23
def test_build_general_proposal():
    candidate = MagicMock()
    candidate.finding_ids = []
    candidate.patch = "diff --git a/x b/x"
    candidate.patch_digest = "sha256:abc123"
    candidate.validated_base_sha = "deadbeef"
    candidate.production_set = ["x.py"]
    candidate.validation_checks = ["check1"]
    candidate.validation_results = ["result1"]
    candidate.candidate_id = "cand-1"
    candidate.created_at = datetime(2026, 10, 10, tzinfo=UTC)

    provenance = MagicMock()
    provenance.problems.return_value = []

    result = build_general_proposal(
        candidate,
        goal="Fix the thing",
        created_by="tester",
        provenance=provenance,
        step_zero={"report": "ok"},
    )

    assert result.goal == "Fix the thing"
    assert result.status.name == "PENDING"
    assert result.created_by == "tester"
    assert result.approval_required is True
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.action_id == "assisted.apply_diff"
    assert action.parameters["patch"] == candidate.patch
    assert action.parameters["patch_digest"] == candidate.patch_digest
    assert action.parameters["validated_base_sha"] == candidate.validated_base_sha
    assert action.parameters["write"] is True
    assert result.scope.files == ["x.py"]
    assert result.constitutional_constraints["candidate_id"] == "cand-1"
    assert result.constitutional_constraints["step_zero"] == {"report": "ok"}
    assert result.provenance is provenance
    provenance.problems.assert_called_once()

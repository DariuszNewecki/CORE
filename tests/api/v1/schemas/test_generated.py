from __future__ import annotations

from api.v1.schemas import IntegrityBaselineResponse


# ID: 180af0c5-b5eb-48e5-a33a-300d4676b4e4
def test_IntegrityBaselineResponse():
    response = IntegrityBaselineResponse(
        label="main-baseline",
        path="src/api/v1",
        files_hashed=42,
    )

    assert response.label == "main-baseline"
    assert response.path == "src/api/v1"
    assert response.files_hashed == 42

    dumped = response.model_dump()
    assert dumped == {
        "label": "main-baseline",
        "path": "src/api/v1",
        "files_hashed": 42,
    }


from api.v1.schemas import ImportViolation, QualityImportsResponse


# ID: 007037f8-a3fa-47ad-8f5f-1c51de3fdedb
def test_QualityImportsResponse() -> None:

    violation_fields = set(ImportViolation.model_fields.keys())

    violation_kwargs: dict = {}
    for field_name, field_info in ImportViolation.model_fields.items():
        annotation = field_info.annotation
        if annotation is str:
            violation_kwargs[field_name] = "value"
        elif annotation is int:
            violation_kwargs[field_name] = 42
        else:
            violation_kwargs[field_name] = "value"

    violation_kwargs["file"] = "src/api/v1/schemas.py"
    if "line" in violation_fields:
        violation_kwargs["line"] = 42
    if "message" in violation_fields:
        violation_kwargs["message"] = "relative import detected"
    if "rule" in violation_fields:
        violation_kwargs["rule"] = "no-relative-imports"

    response = QualityImportsResponse(
        status="ok",
        violations=[violation_kwargs],
    )

    assert response.status == "ok"
    assert len(response.violations) == 1
    assert isinstance(response.violations[0], ImportViolation)
    assert response.model_dump()["status"] == "ok"


# ID: 166961b7-e015-4102-8931-8e6bfe09e3c0
def test_ImportViolation():
    violation = ImportViolation(
        file="src/api/v1/schemas.py",
        line=42,
        rule="no-relative-imports",
        message="Relative import 'from .foo import bar' is not allowed.",
    )

    assert violation.file == "src/api/v1/schemas.py"
    assert violation.line == 42
    assert violation.rule == "no-relative-imports"
    assert violation.message == "Relative import 'from .foo import bar' is not allowed."

    dumped = violation.model_dump()
    assert dumped == {
        "file": "src/api/v1/schemas.py",
        "line": 42,
        "rule": "no-relative-imports",
        "message": "Relative import 'from .foo import bar' is not allowed.",
    }


from api.v1.schemas import LintResponse, LintToolResult


# ID: 73ca1438-6f9d-4ab8-9b70-120d96b16760
def test_LintResponse():
    tool_result = LintToolResult(
        ok=True,
        returncode=0,
        stdout="no issues",
        stderr="",
    )
    response = LintResponse(ok=True, tools={"black": tool_result})

    assert response.ok is True
    assert response.tools == {"black": tool_result}
    assert response.error is None

    dumped = response.model_dump()
    assert dumped["ok"] is True
    assert "black" in dumped["tools"]
    assert dumped["error"] is None


from api.v1.schemas import IntegrateResponse


# ID: 3e3d1ffe-f5b2-4c4b-9686-be38b320d035
def test_IntegrateResponse():
    resp = IntegrateResponse(ok=True, message="integration complete", exit_code=0)

    assert resp.ok is True
    assert resp.message == "integration complete"
    assert resp.error is None
    assert resp.exit_code == 0

    dumped = resp.model_dump()
    assert dumped == {
        "ok": True,
        "message": "integration complete",
        "error": None,
        "exit_code": 0,
    }


from api.v1.schemas import IntegrityVerifyResponse


# ID: 3fd727a0-6b6b-4dbd-a262-c002e8505164
def test_IntegrityVerifyResponse():
    response = IntegrityVerifyResponse(
        label="image-abc",
        ok=True,
        errors=[],
        checked_at="2024-01-01T00:00:00Z",
    )

    assert response.label == "image-abc"
    assert response.ok is True
    assert response.errors == []
    assert response.checked_at == "2024-01-01T00:00:00Z"

    defaulted = IntegrityVerifyResponse(
        label="image-xyz", ok=False, errors=["missing digest"]
    )
    assert defaulted.checked_at is None
    assert defaulted.errors == ["missing digest"]


from api.v1.schemas import CensusDiffResponse


# ID: 2424da4a-e49c-4e5b-88c8-98e4f4a8d5a6
def test_CensusDiffResponse():
    diff_payload = {"added": ["a"], "removed": ["b"], "changed": ["c"]}
    response = CensusDiffResponse(
        available=True,
        baseline="2024-01-01",
        diff=diff_payload,
    )

    assert response.available is True
    assert response.error is None
    assert response.baseline == "2024-01-01"
    assert response.diff == diff_payload

    dumped = response.model_dump()
    assert dumped["available"] is True
    assert dumped["baseline"] == "2024-01-01"
    assert dumped["diff"] == diff_payload


# ID: 48c683d8-8f55-40f2-8c05-e4677d9cfc40
def test_CensusBaselineListResponse():
    from api.v1.schemas import CensusBaselineItem, CensusBaselineListResponse

    baseline = CensusBaselineItem.model_construct()
    response = CensusBaselineListResponse(count=1, baselines=[baseline])

    assert response.count == 1
    assert len(response.baselines) == 1
    assert response.baselines[0] is baseline


from api.v1.schemas import CensusBaselineCreateResponse, CensusBaselineItem


# ID: 896fd7dc-a554-438c-9d2a-e5139b2edd01
def test_CensusBaselineCreateResponse():
    item = CensusBaselineItem.model_construct(name="baseline-1")

    response = CensusBaselineCreateResponse(baseline=item)

    assert isinstance(response, CensusBaselineCreateResponse)
    assert response.baseline is item
    assert response.baseline.name == "baseline-1"


# ID: 8f3e90d7-b505-4029-bce1-81cba7a5a72b
def test_LintToolResult():
    result = LintToolResult(returncode=0, stdout="ok", stderr="")
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.stderr == ""
    assert LintToolResult(returncode=1, stdout="", stderr="boom").returncode == 1


# ID: 22524e92-4d51-4b76-acab-3ed9fe5ac646
def test_CensusBaselineItem():
    item = CensusBaselineItem(name="baseline_a", snapshot_file="snapshots/a.json")

    assert item.name == "baseline_a"
    assert item.snapshot_file == "snapshots/a.json"
    assert item.git_commit is None
    assert item.created_at is None

    item_full = CensusBaselineItem(
        name="baseline_b",
        snapshot_file="snapshots/b.json",
        git_commit="abc123",
        created_at="2024-01-01T00:00:00Z",
    )

    assert item_full.name == "baseline_b"
    assert item_full.snapshot_file == "snapshots/b.json"
    assert item_full.git_commit == "abc123"
    assert item_full.created_at == "2024-01-01T00:00:00Z"


from api.v1.schemas import CensusRunResponse


# ID: 769f6267-9c9a-46f9-bfc0-f7c32c14366c
def test_CensusRunResponse() -> None:
    response = CensusRunResponse(
        run_id="run-123",
        snapshot=True,
        baseline_name="main",
        status="completed",
        requested_at="2024-01-01T00:00:00Z",
        started_at="2024-01-01T00:00:01Z",
        finished_at="2024-01-01T00:00:02Z",
        result={"count": 42},
        error=None,
    )

    assert response.run_id == "run-123"
    assert response.snapshot is True
    assert response.baseline_name == "main"
    assert response.status == "completed"
    assert response.requested_at == "2024-01-01T00:00:00Z"
    assert response.started_at == "2024-01-01T00:00:01Z"
    assert response.finished_at == "2024-01-01T00:00:02Z"
    assert response.result == {"count": 42}
    assert response.error is None


# ID: 6fb0ddd6-8213-4c54-a4c0-74c1685aefaa
def test_SubmitChangeResponse():
    from api.v1.schemas import SubmitChangeResponse

    step_zero = {
        "summary": "Add greeting endpoint",
        "files_reviewed": ["src/api/routes.py"],
        "risk": "low",
    }
    response = SubmitChangeResponse(
        proposal_id="prop-123",
        status="pending_approval",
        approval_required=True,
        scope_files=["src/api/routes.py", "src/api/v1/schemas.py"],
        step_zero=step_zero,
    )

    assert response.proposal_id == "prop-123"
    assert response.status == "pending_approval"
    assert response.approval_required is True
    assert response.scope_files == ["src/api/routes.py", "src/api/v1/schemas.py"]
    assert response.step_zero == step_zero
    assert response.step_zero["risk"] == "low"


from api.v1.schemas import LaneProposeResponse


# ID: b0d1c291-ed1d-4e5d-b3ea-cf0db66cf1eb
def test_LaneProposeResponse() -> None:
    response = LaneProposeResponse(
        proposal_id="prop-123",
        status="pending",
        approval_required=True,
        scope_files=["src/a.py", "src/b.py"],
    )

    assert response.proposal_id == "prop-123"
    assert response.status == "pending"
    assert response.approval_required is True
    assert response.scope_files == ["src/a.py", "src/b.py"]

    dumped = response.model_dump()
    assert dumped == {
        "proposal_id": "prop-123",
        "status": "pending",
        "approval_required": True,
        "scope_files": ["src/a.py", "src/b.py"],
    }


from api.v1.schemas import LaneClaimResponse


# ID: ed64ecf7-5554-4d98-9eb0-139fc9447d95
def test_LaneClaimResponse() -> None:
    response = LaneClaimResponse(
        finding_id="finding-123",
        claimed_by="agent-007",
        status="claimed",
    )

    assert response.finding_id == "finding-123"
    assert response.claimed_by == "agent-007"
    assert response.status == "claimed"

    dumped = response.model_dump()
    assert dumped == {
        "finding_id": "finding-123",
        "claimed_by": "agent-007",
        "status": "claimed",
    }


from api.v1.schemas import LaneFindingListResponse


# ID: 0579f2c1-55b7-499f-b2c0-27cbf309a3d1
def test_LaneFindingListResponse() -> None:
    from api.v1.schemas import LaneFindingItem

    item = LaneFindingItem.model_construct()
    item.__dict__["severity"] = "medium"

    response = LaneFindingListResponse(count=1, findings=[item])

    assert response.count == 1
    assert len(response.findings) == 1
    assert isinstance(response.findings[0], LaneFindingItem)
    assert response.findings[0].severity == "medium"

    empty = LaneFindingListResponse(count=0, findings=[])
    assert empty.count == 0
    assert empty.findings == []


from unittest.mock import MagicMock

from api.v1.schemas import LaneBundle, LaneFindingWithBundle


# ID: fd4a5fce-ea89-40de-a5e4-8caa9232313b
def test_LaneFindingWithBundle():
    bundle = MagicMock(spec=LaneBundle)
    finding = LaneFindingWithBundle.model_construct(bundle=bundle)
    assert isinstance(finding, LaneFindingWithBundle)
    assert finding.bundle is bundle


from api.v1.schemas import LaneFindingItem


# ID: cd8fcb74-5f77-4b46-8adf-a59d4ede7285
def test_LaneFindingItem():
    item = LaneFindingItem(
        id="finding-1",
        subject="remediation.lane.finding",
        payload={"k": "v", "n": 1},
    )

    assert item.id == "finding-1"
    assert item.subject == "remediation.lane.finding"
    assert item.payload == {"k": "v", "n": 1}
    assert item.created_at is None

    item_with_time = LaneFindingItem(
        id="finding-2",
        subject="remediation.lane.finding",
        payload={},
        created_at="2024-01-01T00:00:00Z",
    )
    assert item_with_time.created_at == "2024-01-01T00:00:00Z"
    assert item_with_time.payload == {}

    dumped = item.model_dump()
    assert dumped == {
        "id": "finding-1",
        "subject": "remediation.lane.finding",
        "payload": {"k": "v", "n": 1},
        "created_at": None,
    }


from unittest.mock import patch


# ID: 76fa1fe2-8333-4f9a-aabd-dcf0f2a4e2a5
def test_LaneBundle():
    with patch("api.v1.schemas.LaneBundleRule") as MockRule:
        mock_rule = MockRule.return_value

        bundle = LaneBundle.model_construct(rule=mock_rule)

        assert bundle.rule is mock_rule
        assert bundle.remediation is None

        bundle_with_remediation = LaneBundle.model_construct(
            rule=mock_rule,
            remediation={"fix": "apply patch"},
        )
        assert bundle_with_remediation.rule is mock_rule
        assert bundle_with_remediation.remediation == {"fix": "apply patch"}


from api.v1.schemas import LaneBundleRule


# ID: 7b576ccb-1c71-4358-9e93-e912bb9f568c
def test_LaneBundleRule():
    rule = LaneBundleRule(
        id="ADR-109",
        rationale="Ensures lane bundle traceability",
        in_registry=True,
    )

    assert rule.id == "ADR-109"
    assert rule.rationale == "Ensures lane bundle traceability"
    assert rule.in_registry is True


# ID: 61c878f3-16b9-4937-9221-bdd66f127253
def test_ProposalResponse():
    from api.v1.schemas import ProposalActionItem, ProposalResponse

    action = ProposalActionItem(
        action_id="act-1",
        action_type="modify_file",
        target="a.py",
    )

    proposal = ProposalResponse(
        proposal_id="prop-123",
        goal="Improve coverage",
        actions=[action],
        scope={"files": ["a.py"]},
        risk={"level": "low"},
        status="pending",
        created_at="2024-01-01T00:00:00Z",
        created_by="alice",
        validation_checks={"ok": True},
        validation_results={"passed": 3},
        approval_required=True,
        approved_by="bob",
        approved_at="2024-01-02T00:00:00Z",
        approval_authority="council",
        failure_reason=None,
    )

    assert proposal.proposal_id == "prop-123"
    assert proposal.goal == "Improve coverage"
    assert proposal.actions == [action]
    assert proposal.actions[0].action_id == "act-1"
    assert proposal.scope == {"files": ["a.py"]}
    assert proposal.risk == {"level": "low"}
    assert proposal.status == "pending"
    assert proposal.created_at == "2024-01-01T00:00:00Z"
    assert proposal.created_by == "alice"
    assert proposal.approval_required is True
    assert proposal.approved_by == "bob"
    assert proposal.approved_at == "2024-01-02T00:00:00Z"
    assert proposal.approval_authority == "council"
    assert proposal.failure_reason is None


from api.v1.schemas import ProposalActionItem


# ID: cde11213-6ed9-47d6-8009-ab6b84b160b2
def test_ProposalActionItem():
    item = ProposalActionItem(
        action_id="act-1",
        flow_id="flow-1",
        parameters={"key": "value", "num": 42},
        order=3,
    )

    assert item.action_id == "act-1"
    assert item.flow_id == "flow-1"
    assert item.parameters == {"key": "value", "num": 42}
    assert item.order == 3

    default_item = ProposalActionItem()
    assert default_item.action_id is None
    assert default_item.flow_id is None
    assert default_item.parameters == {}
    assert default_item.order == 0


from api.v1.schemas import GovernanceChainResponse


# ID: a75a6f05-6efa-4e53-b190-52afe5253c03
def test_GovernanceChainResponse() -> None:
    response = GovernanceChainResponse(
        proposal={
            "proposal_id": "p1",
            "title": "Test Proposal",
            "status": "approved",
            "goal": "Ship the feature",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
    )

    assert response.proposal is not None
    assert response.proposal.proposal_id == "p1"
    assert response.findings == []
    assert response.consequence is None


from api.v1.schemas import ConsequenceRecord


# ID: c34bd983-ac6c-4a39-bea3-35867d4e7df2
def test_ConsequenceRecord():
    # happy path: construct with full data
    record = ConsequenceRecord(
        pre_execution_sha="abc123",
        post_execution_sha="def456",
        files_changed=["a.py", "b.py"],
        findings_resolved=[{"id": 1}],
        authorized_by_rules=[{"rule": "r1"}],
        recorded_at="2024-01-01T00:00:00Z",
    )
    assert record.pre_execution_sha == "abc123"
    assert record.post_execution_sha == "def456"
    assert record.files_changed == ["a.py", "b.py"]
    assert record.findings_resolved == [{"id": 1}]
    assert record.authorized_by_rules == [{"rule": "r1"}]
    assert record.recorded_at == "2024-01-01T00:00:00Z"

    # defaults: optional SHAs default to None, lists default to empty
    default_record = ConsequenceRecord(recorded_at="2024-01-02T00:00:00Z")
    assert default_record.pre_execution_sha is None
    assert default_record.post_execution_sha is None
    assert default_record.files_changed == []
    assert default_record.findings_resolved == []
    assert default_record.authorized_by_rules == []


from api.v1.schemas import ProposalSummary


# ID: 6af9bf3c-1d8a-41ff-b508-b81d059b00dd
def test_ProposalSummary():
    summary = ProposalSummary(
        proposal_id="prop-123",
        goal="Increase coverage",
        status="approved",
        risk={"level": "low"},
        approval_authority="governance-board",
        approved_by="alice",
        approved_at="2024-01-01T00:00:00Z",
        execution_results={"ok": True},
        created_by="bob",
        created_at="2023-12-31T00:00:00Z",
        failure_reason=None,
    )

    assert summary.proposal_id == "prop-123"
    assert summary.goal == "Increase coverage"
    assert summary.status == "approved"
    assert summary.risk == {"level": "low"}
    assert summary.approval_authority == "governance-board"
    assert summary.approved_by == "alice"
    assert summary.approved_at == "2024-01-01T00:00:00Z"
    assert summary.execution_results == {"ok": True}
    assert summary.created_by == "bob"
    assert summary.created_at == "2023-12-31T00:00:00Z"
    assert summary.failure_reason is None

    minimal = ProposalSummary(
        proposal_id="prop-456",
        goal="Minimal",
        status="pending",
        created_at="2024-01-02T00:00:00Z",
    )
    assert minimal.risk is None
    assert minimal.approval_authority is None
    assert minimal.approved_by is None
    assert minimal.approved_at is None
    assert minimal.execution_results is None
    assert minimal.created_by is None
    assert minimal.failure_reason is None


from api.v1.schemas import FindingEvidence


# ID: 7b560881-ba9c-4035-90d6-6183de54ae6c
def test_FindingEvidence():
    evidence_payload = {"lines": [1, 2, 3], "snippet": "def foo(): pass"}

    finding = FindingEvidence(
        entry_id="entry-123",
        subject="src/foo.py",
        status="open",
        check_id="check-abc",
        rule_id="rule-42",
        file_path="src/foo.py",
        severity="high",
        evidence=evidence_payload,
        evidence_class="CodeSnippet",
        created_at="2024-01-01T00:00:00Z",
    )

    assert finding.entry_id == "entry-123"
    assert finding.subject == "src/foo.py"
    assert finding.status == "open"
    assert finding.check_id == "check-abc"
    assert finding.rule_id == "rule-42"
    assert finding.file_path == "src/foo.py"
    assert finding.severity == "high"
    assert finding.evidence == evidence_payload
    assert finding.evidence_class == "CodeSnippet"
    assert finding.created_at == "2024-01-01T00:00:00Z"


from api.v1.schemas import RemediationRunResponse


# ID: 6d715837-be2b-4c96-ace7-b956b3652fc2
def test_RemediationRunResponse():
    payload = {
        "run_id": "run-123",
        "audit_run_id": "audit-456",
        "mode": "auto",
        "write": True,
        "status": "completed",
        "requested_by": "user-1",
        "requested_at": "2024-01-01T00:00:00Z",
        "started_at": "2024-01-01T00:00:01Z",
        "finished_at": "2024-01-01T00:00:02Z",
        "result": {"remediated": 3},
        "error": None,
    }

    response = RemediationRunResponse(**payload)

    assert response.run_id == "run-123"
    assert response.audit_run_id == "audit-456"
    assert response.mode == "auto"
    assert response.write is True
    assert response.status == "completed"
    assert response.requested_by == "user-1"
    assert response.requested_at == "2024-01-01T00:00:00Z"
    assert response.started_at == "2024-01-01T00:00:01Z"
    assert response.finished_at == "2024-01-01T00:00:02Z"
    assert response.result == {"remediated": 3}
    assert response.error is None

    dumped = response.model_dump()
    assert dumped["run_id"] == "run-123"
    assert dumped["result"] == {"remediated": 3}


from api.v1.schemas import FixCommandListResponse


# ID: 04ef555f-ef3a-4779-b3b3-83e8f526c7b9
def test_FixCommandListResponse():
    response = FixCommandListResponse(
        count=1,
        commands=[
            {
                "action_id": "restart_service",
                "title": "Restart Service",
                "description": "Restarts the target service.",
            }
        ],
    )

    assert isinstance(response, FixCommandListResponse)
    assert response.count == 1
    assert isinstance(response.commands, list)
    assert len(response.commands) == 1
    assert response.commands[0].action_id == "restart_service"


from api.v1.schemas import ActionCommandItem


# ID: 9ab2289c-6e01-42df-a07c-ece0fd40fe4f
def test_ActionCommandItem():
    item = ActionCommandItem(
        action_id="fix.imports.unused",
        description="Remove unused imports",
        category="cleanup",
        policies=["policy-a", "policy-b"],
        impact_level="low",
        requires_db=True,
        requires_vectors=False,
        remediates=["unused_import"],
    )

    assert item.action_id == "fix.imports.unused"
    assert item.description == "Remove unused imports"
    assert item.category == "cleanup"
    assert item.policies == ["policy-a", "policy-b"]
    assert item.impact_level == "low"
    assert item.requires_db is True
    assert item.requires_vectors is False
    assert item.remediates == ["unused_import"]

    minimal = ActionCommandItem(action_id="noop")

    assert minimal.action_id == "noop"
    assert minimal.description is None
    assert minimal.category is None
    assert minimal.policies == []
    assert minimal.impact_level is None
    assert minimal.requires_db is False
    assert minimal.requires_vectors is False
    assert minimal.remediates == []

    assert minimal.model_dump()["action_id"] == "noop"

    assert ActionCommandItem.model_validate({"action_id": "x"}).action_id == "x"

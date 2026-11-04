from __future__ import annotations

from will.autonomy.proposal import ProposalConsequence


# ID: e5c55301-71ea-4f8f-808c-29e458816949
def test_ProposalConsequence():
    consequence = ProposalConsequence(
        proposal_id="prop-123",
        pre_execution_sha="abc123",
        post_execution_sha="def456",
        files_changed=[{"path": "src/will/autonomy/proposal.py"}],
        findings_resolved=["F-1", "F-2"],
        authorized_by_rules=["ADR-133"],
    )

    assert consequence.proposal_id == "prop-123"
    assert consequence.pre_execution_sha == "abc123"
    assert consequence.post_execution_sha == "def456"
    assert consequence.files_changed == [{"path": "src/will/autonomy/proposal.py"}]
    assert consequence.findings_resolved == ["F-1", "F-2"]
    assert consequence.authorized_by_rules == ["ADR-133"]
    assert consequence.recorded_at is None

    minimal = ProposalConsequence(proposal_id="prop-456")
    assert minimal.pre_execution_sha is None
    assert minimal.post_execution_sha is None
    assert minimal.files_changed == []
    assert minimal.findings_resolved == []
    assert minimal.authorized_by_rules == []
    assert minimal.recorded_at is None

    # default_factory must yield independent list instances per instance
    assert minimal.files_changed is not consequence.files_changed


from unittest.mock import MagicMock, patch

from will.autonomy.proposal import (
    Proposal,
    ProposalProvenance,
    ProposalStatus,
)


# ID: 67128359-7430-4ded-9fa6-1486da40a9c4
def test_Proposal_from_dict():
    data = {
        "proposal_id": "prop-123",
        "goal": "do things",
        "actions": [
            {
                "action_id": "a1",
                "parameters": {"x": 1},
                "order": 2,
            }
        ],
        "scope": {
            "files": ["a.py"],
            "modules": ["m"],
            "symbols": ["s"],
            "policies": ["p"],
        },
        "risk": {
            "overall_risk": 0.5,
            "action_risks": {"a1": 0.5},
            "risk_factors": ["f"],
            "mitigation": ["m"],
        },
        "status": ProposalStatus.PENDING.value,
        "created_at": "2024-01-01T00:00:00",
        "constitutional_constraints": {"provenance": {"source": "test"}},
    }

    with patch(
        "will.autonomy.proposal.ProposalProvenance.from_dict",
        return_value=MagicMock(spec=ProposalProvenance),
    ) as mock_prov:
        proposal = Proposal.from_dict(data)

    assert isinstance(proposal, Proposal)
    assert proposal.proposal_id == "prop-123"
    assert proposal.goal == "do things"
    assert len(proposal.actions) == 1
    assert proposal.actions[0].action_id == "a1"
    assert proposal.actions[0].parameters == {"x": 1}
    assert proposal.actions[0].order == 2
    assert proposal.scope.files == ["a.py"]
    assert proposal.scope.modules == ["m"]
    assert proposal.risk is not None
    assert proposal.risk.overall_risk == 0.5
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.constitutional_constraints == {"provenance": {"source": "test"}}
    assert proposal.provenance is not None
    mock_prov.assert_called_once_with({"source": "test"})


from datetime import UTC, datetime


# ID: 88ea3f45-a280-4123-8771-0ba7db6ccaca
def test_Proposal_to_dict():
    # Build a minimal proposal instance, bypassing __init__ to avoid
    # unrelated construction requirements.
    proposal = Proposal.__new__(Proposal)

    proposal.proposal_id = "prop-123"
    proposal.goal = "Improve coverage"

    action = MagicMock()
    action.action_id = "act-1"
    action.flow_id = "flow-1"
    action.parameters = {"k": "v"}
    action.order = 0
    proposal.actions = [action]

    scope = MagicMock()
    scope.files = ["a.py"]
    scope.modules = ["mod"]
    scope.symbols = ["sym"]
    scope.policies = ["pol"]
    proposal.scope = scope

    risk = MagicMock()
    risk.overall_risk = "low"
    risk.action_risks = {"act-1": "low"}
    risk.risk_factors = []
    risk.mitigation = "none"
    proposal.risk = risk

    proposal.status = MagicMock()
    proposal.status.value = "proposed"

    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    proposal.created_at = created_at
    proposal.created_by = "tester"
    proposal.validation_checks = ["c1"]
    proposal.validation_results = {"c1": True}
    proposal.execution_started_at = None
    proposal.execution_completed_at = None
    proposal.execution_results = {}
    proposal.approval_required = True
    proposal.approved_by = None
    proposal.approved_at = None
    proposal.approval_authority = None
    proposal.failure_reason = None

    constraints = {"max_files": 5}
    proposal.constraints_for_storage = MagicMock(return_value=constraints)

    result = proposal.to_dict()

    assert result["proposal_id"] == "prop-123"
    assert result["goal"] == "Improve coverage"
    assert result["actions"] == [
        {
            "action_id": "act-1",
            "flow_id": "flow-1",
            "parameters": {"k": "v"},
            "order": 0,
        }
    ]
    assert result["scope"] == {
        "files": ["a.py"],
        "modules": ["mod"],
        "symbols": ["sym"],
        "policies": ["pol"],
    }
    assert result["risk"] == {
        "overall_risk": "low",
        "action_risks": {"act-1": "low"},
        "risk_factors": [],
        "mitigation": "none",
    }
    assert result["status"] == "proposed"
    assert result["created_at"] == created_at.isoformat()
    assert result["created_by"] == "tester"
    assert result["validation_checks"] == ["c1"]
    assert result["validation_results"] == {"c1": True}
    assert result["execution_started_at"] is None
    assert result["execution_completed_at"] is None
    assert result["execution_results"] == {}
    assert result["constitutional_constraints"] == constraints
    assert result["approval_required"] is True
    assert result["approved_by"] is None
    assert result["approved_at"] is None
    assert result["approval_authority"] is None
    assert result["failure_reason"] is None
    proposal.constraints_for_storage.assert_called_once()


# ID: 0229f9c5-8fcd-4308-82fc-c9c29a4c16b6
def test_Proposal_constraints_for_storage():
    proposal = MagicMock(spec=Proposal)
    proposal.constitutional_constraints = {"max_risk": "low"}
    provenance = MagicMock()
    provenance.to_dict = MagicMock(return_value={"source": "test"})
    proposal.provenance = provenance

    result = Proposal.constraints_for_storage(proposal)

    assert result == {"max_risk": "low", "provenance": {"source": "test"}}
    provenance.to_dict.assert_called_once()
    assert proposal.constitutional_constraints == {"max_risk": "low"}





# ID: da1c7404-f663-40dc-9a8a-ac4cf3a63255
def test_Proposal_compute_risk() -> None:
    proposal = Proposal.__new__(Proposal)

    action = MagicMock()
    action.action_id = "act-1"
    action.flow_id = None
    proposal.actions = [action]

    scope = MagicMock()
    scope.files = ["a.py", "b.py"]
    proposal.scope = scope

    mock_registry = MagicMock()
    mock_registry.get = MagicMock(return_value=object())

    mock_risk_mapping = {"act-1": "safe"}

    with (
        patch("body.atomic.registry.action_registry", mock_registry),
        patch(
            "shared.infrastructure.intent.action_risk.load_action_risk",
            return_value=mock_risk_mapping,
        ),
        patch("will.autonomy.proposal._resolve_impact", return_value="safe"),
    ):
        risk = proposal.compute_risk()

    assert risk.overall_risk == "safe"
    assert risk.action_risks == {"act-1": "safe"}
    assert risk.risk_factors == []
    assert risk.mitigation == []
    assert proposal.risk is risk
    assert proposal.approval_required == risk.requires_approval()

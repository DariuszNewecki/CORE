from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: 16ba3e4e-8c4d-48b0-b255-26fddf21947d
def test_ProposalMapper_update_db_model():
    from will.autonomy.proposal_mapper import ProposalMapper

    proposal = MagicMock()
    proposal.goal = "ship it"
    proposal.status.value = "pending"
    proposal.actions = [
        MagicMock(action_id="a1", flow_id="f1", parameters={"k": "v"}, order=1),
        MagicMock(action_id="a2", flow_id="f2", parameters={}, order=2),
    ]
    proposal.scope.files = ["a.py"]
    proposal.scope.modules = ["m"]
    proposal.scope.symbols = ["s"]
    proposal.scope.policies = ["p"]
    proposal.risk.overall_risk = "low"
    proposal.risk.action_risks = {"a1": "low"}
    proposal.risk.risk_factors = []
    proposal.risk.mitigation = "none"
    proposal.validation_checks = {"checks": "ok"}
    proposal.validation_results = {"results": "ok"}
    proposal.execution_started_at = "start"
    proposal.execution_completed_at = "end"
    proposal.execution_results = {"done": True}
    proposal.constraints_for_storage.return_value = {"constraints": []}
    proposal.approval_required = True
    proposal.approved_by = "alice"
    proposal.approved_at = "now"
    proposal.approval_authority = "admin"
    proposal.failure_reason = None

    db_proposal = MagicMock()

    with patch(
        "will.autonomy.proposal_mapper._sanitize_payload",
        side_effect=lambda x: x,
    ) as mock_sanitize:
        ProposalMapper.update_db_model(db_proposal, proposal)

    assert db_proposal.goal == "ship it"
    assert db_proposal.status == "pending"
    assert db_proposal.actions == [
        {"action_id": "a1", "flow_id": "f1", "parameters": {"k": "v"}, "order": 1},
        {"action_id": "a2", "flow_id": "f2", "parameters": {}, "order": 2},
    ]
    assert db_proposal.scope == {
        "files": ["a.py"],
        "modules": ["m"],
        "symbols": ["s"],
        "policies": ["p"],
    }
    assert db_proposal.risk == {
        "overall_risk": "low",
        "action_risks": {"a1": "low"},
        "risk_factors": [],
        "mitigation": "none",
    }
    assert db_proposal.validation_checks == {"checks": "ok"}
    assert db_proposal.validation_results == {"results": "ok"}
    assert db_proposal.execution_started_at == "start"
    assert db_proposal.execution_completed_at == "end"
    assert db_proposal.execution_results == {"done": True}
    assert db_proposal.constitutional_constraints == {"constraints": []}
    assert db_proposal.approval_required is True
    assert db_proposal.approved_by == "alice"
    assert db_proposal.approved_at == "now"
    assert db_proposal.approval_authority == "admin"
    assert db_proposal.failure_reason is None
    assert mock_sanitize.call_count == 4


from datetime import UTC, datetime


# ID: ff3d43de-3da7-4986-ba6d-a46bcd11b4f3
def test_ProposalMapper_from_db_model():
    from will.autonomy.proposal_mapper import ProposalMapper

    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    db_proposal = MagicMock()
    db_proposal.proposal_id = "prop-123"
    db_proposal.goal = "Test goal"
    db_proposal.actions = ["action1", "action2"]
    db_proposal.scope = "test-scope"
    db_proposal.risk = "low"
    db_proposal.status = "pending"
    db_proposal.created_at = created_at
    db_proposal.created_by = "tester"
    db_proposal.validation_checks = ["check1"]
    db_proposal.validation_results = {"check1": True}
    db_proposal.execution_started_at = None
    db_proposal.execution_completed_at = None
    db_proposal.execution_results = {}
    db_proposal.constitutional_constraints = []
    db_proposal.approval_required = False
    db_proposal.approved_by = None
    db_proposal.approved_at = None
    db_proposal.approval_authority = None
    db_proposal.failure_reason = None

    expected_proposal = MagicMock()

    with patch(
        "will.autonomy.proposal_mapper.Proposal.from_dict",
        return_value=expected_proposal,
    ) as mock_from_dict:
        result = ProposalMapper.from_db_model(db_proposal)

    mock_from_dict.assert_called_once()
    call_data = mock_from_dict.call_args[0][0]
    assert call_data["proposal_id"] == "prop-123"
    assert call_data["goal"] == "Test goal"
    assert call_data["created_at"] == created_at.isoformat()
    assert call_data["execution_started_at"] is None
    assert call_data["execution_completed_at"] is None
    assert call_data["approved_at"] is None
    assert result is expected_proposal



from will.autonomy.proposal_mapper import ProposalMapper


# ID: f62de811-dc9b-469c-bfb5-de5b1be55546
def test_ProposalMapper_to_db_model():
    scope = MagicMock()
    scope.files = ["src/a.py"]
    scope.modules = ["will.autonomy"]
    scope.symbols = ["Foo.bar"]
    scope.policies = ["no-force-push"]

    action = MagicMock()
    action.action_id = "act-1"
    action.flow_id = "flow-1"
    action.parameters = {"key": "value"}
    action.order = 0

    risk = MagicMock()
    risk.overall_risk = "medium"
    risk.action_risks = {"act-1": "low"}
    risk.risk_factors = ["time"]
    risk.mitigation = "none"

    created_at = datetime(2024, 1, 1, tzinfo=UTC)

    proposal = MagicMock()
    proposal.proposal_id = "prop-123"
    proposal.goal = "Achieve something"
    proposal.status.value = "draft"
    proposal.actions = [action]
    proposal.scope = scope
    proposal.risk = risk
    proposal.created_at = created_at
    proposal.created_by = "agent"
    proposal.validation_checks = [{"check": "ok"}]
    proposal.validation_results = [{"result": "pass"}]
    proposal.execution_started_at = None
    proposal.execution_completed_at = None
    proposal.execution_results = {"done": True}
    proposal.constraints_for_storage = MagicMock(return_value=[{"c": 1}])
    proposal.approval_required = False
    proposal.approved_by = None
    proposal.approved_at = None
    proposal.approval_authority = None
    proposal.failure_reason = None

    db_class = MagicMock(return_value=MagicMock(name="db_model"))

    mapper = ProposalMapper()
    with patch(
        "will.autonomy.proposal_mapper._sanitize_payload",
        side_effect=lambda x: x,
    ) as mock_sanitize:
        result = mapper.to_db_model(proposal, db_class)

    db_class.assert_called_once()
    kwargs = db_class.call_args.kwargs

    assert kwargs["proposal_id"] == "prop-123"
    assert kwargs["goal"] == "Achieve something"
    assert kwargs["status"] == "draft"
    assert kwargs["actions"] == [
        {
            "action_id": "act-1",
            "flow_id": "flow-1",
            "parameters": {"key": "value"},
            "order": 0,
        }
    ]
    assert kwargs["scope"] == {
        "files": ["src/a.py"],
        "modules": ["will.autonomy"],
        "symbols": ["Foo.bar"],
        "policies": ["no-force-push"],
    }
    assert kwargs["risk"] == {
        "overall_risk": "medium",
        "action_risks": {"act-1": "low"},
        "risk_factors": ["time"],
        "mitigation": "none",
    }
    assert kwargs["created_at"] == created_at
    assert kwargs["created_by"] == "agent"
    assert kwargs["approval_required"] is False
    assert result is db_class.return_value
    assert mock_sanitize.call_count >= 1

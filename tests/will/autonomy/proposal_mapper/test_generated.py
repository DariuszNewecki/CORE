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

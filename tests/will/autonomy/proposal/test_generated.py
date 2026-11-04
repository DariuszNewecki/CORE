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

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


# ID: 8c54d354-6683-46dd-bfa6-c95da08d1107
def test_Proposal_check_submission():
    from unittest.mock import MagicMock

    from will.autonomy.proposal import Proposal

    proposal = Proposal.__new__(Proposal)

    proposal.goal = "Do the thing"

    action = MagicMock()
    action.ref_kind = "action"
    action.ref_id = "some.action"
    action.validate_exists = MagicMock(return_value=True)
    proposal.actions = [action]

    scope = MagicMock()
    scope.files = ["src/will/autonomy/proposal.py"]
    proposal.scope = scope

    provenance = MagicMock()
    provenance.problems = MagicMock(return_value=[])
    proposal.provenance = provenance

    errors = Proposal.check_submission(proposal)

    assert errors == []
    action.validate_exists.assert_called_once_with()
    provenance.problems.assert_called_once_with()


# ID: 26f0546b-a4e1-4f28-9d9b-37f08d552392
def test_Proposal_validate():
    proposal = Proposal.__new__(Proposal)
    proposal.check_submission = MagicMock(return_value=[])
    proposal.risk = MagicMock()
    proposal.risk.overall_risk = "low"
    proposal.approved_by = []

    is_valid, errors = Proposal.validate(proposal)

    proposal.check_submission.assert_called_once_with()
    assert is_valid is True
    assert errors == []


# ID: dd0dd37e-d284-4936-a7b4-6faab6f7e73b
def test_Proposal() -> None:
    from will.autonomy.proposal import ProposalAction, ProposalScope, RiskAssessment

    scope = ProposalScope(files=["src/will/autonomy/proposal.py"])
    actions = [
        ProposalAction(action_id="act-1", parameters={}, order=0),
    ]
    risk = RiskAssessment(
        overall_risk="moderate",
        action_risks={"act-1": "moderate"},
        risk_factors=["Contains moderate-impact actions"],
        mitigation=["Automated pre-flight checks"],
    )
    provenance = MagicMock()
    provenance.to_dict.return_value = {"anchor": "x"}

    proposal = Proposal(
        goal="Test goal",
        actions=actions,
        scope=scope,
        risk=risk,
        provenance=provenance,
    )

    assert proposal.goal == "Test goal"
    assert proposal.actions == actions
    assert proposal.scope is scope
    assert proposal.risk is risk
    assert proposal.created_by == "autonomous"

    storage = proposal.constraints_for_storage()
    assert storage["provenance"] == {"anchor": "x"}

    data = proposal.to_dict()
    assert data["goal"] == "Test goal"
    assert data["risk"]["overall_risk"] == "moderate"
    assert data["status"] == proposal.status.value


from will.autonomy.proposal import ProposalAction


# ID: 1a537bfe-0e18-48d6-b9e0-be15cfa55c4f
def test_ProposalAction_validate_exists() -> None:
    action = ProposalAction.__new__(ProposalAction)
    action.action_id = "sample_action"
    action.flow_id = None

    mock_registry = MagicMock()
    mock_registry.get.return_value = object()

    with patch("body.atomic.registry.action_registry", mock_registry):
        assert action.validate_exists() is True

    mock_registry.get.assert_called_once_with("sample_action")


# ID: c775be4f-9490-4a26-bd6a-d5b7b1f551ac
def test_ProposalAction_ref_kind():
    action_obj = MagicMock(spec=ProposalAction)
    action_obj.action_id = "action-123"
    action_obj.flow_id = None
    assert ProposalAction.ref_kind.__get__(action_obj, ProposalAction) == "action"

    flow_obj = MagicMock(spec=ProposalAction)
    flow_obj.action_id = None
    flow_obj.flow_id = "flow-456"
    assert ProposalAction.ref_kind.__get__(flow_obj, ProposalAction) == "flow"


# ID: ad6f7e8b-cdbf-4f8a-a2ea-f01f1be6a9fc
def test_ProposalAction_ref_id():
    action = MagicMock(spec=ProposalAction)
    action.action_id = "action-123"
    action.flow_id = "flow-456"
    action.ref_id = ProposalAction.ref_id.__get__(action, ProposalAction)
    assert action.ref_id == "action-123"

    action2 = MagicMock(spec=ProposalAction)
    action2.action_id = None
    action2.flow_id = "flow-456"
    action2.ref_id = ProposalAction.ref_id.__get__(action2, ProposalAction)
    assert action2.ref_id == "flow-456"


# ID: 3205a492-59f2-4fb2-821d-9a40103f7d44
def test_ProposalAction() -> None:
    from will.autonomy.proposal import ProposalAction

    # Happy path: action_id set, flow_id None
    action = ProposalAction(action_id="fix.format", parameters={"x": 1}, order=3)

    assert action.action_id == "fix.format"
    assert action.flow_id is None
    assert action.parameters == {"x": 1}
    assert action.order == 3
    assert action.ref_id == "fix.format"
    assert action.ref_kind == "action"

    # validate_exists should consult the action registry
    mock_registry = MagicMock()
    mock_registry.get.return_value = MagicMock()
    with patch("body.atomic.registry.action_registry", mock_registry):
        assert action.validate_exists() is True
    mock_registry.get.assert_called_once_with("fix.format")

    # Happy path: flow_id set, action_id None
    flow = ProposalAction(flow_id="flow.fix_code")
    assert flow.action_id is None
    assert flow.flow_id == "flow.fix_code"
    assert flow.ref_id == "flow.fix_code"
    assert flow.ref_kind == "flow"

    mock_flow_registry = MagicMock()
    mock_flow_registry.get.return_value = MagicMock()
    with patch("body.flows.registry.flow_registry", mock_flow_registry):
        assert flow.validate_exists() is True
    mock_flow_registry.get.assert_called_once_with("flow.fix_code")


from will.autonomy.proposal import RiskAssessment


# ID: 7ff22984-4094-4596-81a6-10399f417694
def test_RiskAssessment_requires_approval() -> None:
    assert RiskAssessment(overall_risk="moderate").requires_approval() is True
    assert RiskAssessment(overall_risk="high").requires_approval() is True
    assert RiskAssessment(overall_risk="low").requires_approval() is False


# ID: a49640ea-9185-4938-8aef-deb28142d61a
def test_RiskAssessment():
    # Happy path: safe risk does not require approval
    safe = RiskAssessment(overall_risk="safe")
    assert safe.overall_risk == "safe"
    assert safe.action_risks == {}
    assert safe.risk_factors == []
    assert safe.mitigation == []
    assert safe.requires_approval() is False

    # Moderate and high risk require approval
    moderate = RiskAssessment(overall_risk="moderate")
    assert moderate.requires_approval() is True

    high = RiskAssessment(
        overall_risk="high",
        action_risks={"action-1": "critical"},
        risk_factors=["destructive change"],
        mitigation=["manual review"],
    )
    assert high.requires_approval() is True
    assert high.action_risks == {"action-1": "critical"}
    assert high.risk_factors == ["destructive change"]
    assert high.mitigation == ["manual review"]


# ID: b0469d51-af61-403d-a0ef-bc91f8fa50cc
def test_ProposalProvenance_from_dict():
    data = {
        "anchor_kind": "issue",
        "anchor_refs": [1, 2, 3],
        "problem_owner": "team-alpha",
        "producer": "worker-x",
        "retires": [10, 20],
    }

    result = ProposalProvenance.from_dict(data)

    assert isinstance(result, ProposalProvenance)
    assert result.anchor_kind == "issue"
    assert result.anchor_refs == ["1", "2", "3"]
    assert result.problem_owner == "team-alpha"
    assert result.producer == "worker-x"
    assert result.retires == ["10", "20"]


# ID: 15f3a70d-9c08-492f-af67-1431329e462c
def test_ProposalProvenance_to_dict():
    provenance = ProposalProvenance(
        anchor_kind="finding",
        anchor_refs=("ref-1", "ref-2"),
        problem_owner="owner-a",
        producer="producer-b",
        retires=("r-1", "r-2"),
    )

    result = provenance.to_dict()

    assert result == {
        "anchor_kind": "finding",
        "anchor_refs": ["ref-1", "ref-2"],
        "problem_owner": "owner-a",
        "producer": "producer-b",
        "retires": ["r-1", "r-2"],
    }
    assert isinstance(result["anchor_refs"], list)
    assert isinstance(result["retires"], list)


# ID: 3e73cdcc-58d5-4010-a337-a462fed1b776
def test_ProposalProvenance_problems() -> None:
    provenance = MagicMock()
    provenance.anchor_kind = "adr"
    provenance.anchor_refs = ["ADR-133"]
    provenance.problem_owner = "core"
    provenance.producer = "will"

    result = ProposalProvenance.problems(provenance)

    assert result == []


# ID: c54ac342-1bbe-4fae-a55a-6f3ba5997607
def test_ProposalProvenance() -> None:
    provenance = ProposalProvenance(
        anchor_kind="adr",
        anchor_refs=["ADR-168"],
        problem_owner="core",
        producer="core",
        retires=["ADR-100"],
    )

    # Happy path: well-formed provenance reports no problems.
    assert provenance.problems() == []

    # Round-trip serialisation preserves the fields.
    data = provenance.to_dict()
    assert data == {
        "anchor_kind": "adr",
        "anchor_refs": ["ADR-168"],
        "problem_owner": "core",
        "producer": "core",
        "retires": ["ADR-100"],
    }

    restored = ProposalProvenance.from_dict(data)
    assert restored == provenance
    assert restored.problems() == []

    # Default retires is empty and still valid.
    default_retires = ProposalProvenance(
        anchor_kind="governor_request",
        anchor_refs=["REQ-1"],
        problem_owner="governor",
        producer="governor",
    )
    assert default_retires.retires == []
    assert default_retires.problems() == []


from will.autonomy.proposal import ProposalScope


# ID: a06307ed-2454-48b4-aa60-febc15f4ce63
def test_ProposalScope_conflicts_with() -> None:
    scope_a = ProposalScope(
        files=["src/a.py", "src/b.py"],
        modules=["mod_a"],
        symbols=["sym_a"],
    )
    scope_b = ProposalScope(
        files=["src/b.py", "src/c.py"],
        modules=["mod_b"],
        symbols=["sym_b"],
    )

    # Overlapping files -> conflict
    assert scope_a.conflicts_with(scope_b) is True
    assert scope_b.conflicts_with(scope_a) is True

    # No overlap -> no conflict
    scope_c = ProposalScope(
        files=["src/x.py"],
        modules=["mod_x"],
        symbols=["sym_x"],
    )
    assert scope_a.conflicts_with(scope_c) is False
    assert scope_c.conflicts_with(scope_a) is False

    # Overlapping modules only -> conflict
    scope_d = ProposalScope(
        files=["src/y.py"],
        modules=["mod_a"],
        symbols=["sym_y"],
    )
    assert scope_a.conflicts_with(scope_d) is True

    # Overlapping symbols only -> conflict
    scope_e = ProposalScope(
        files=["src/z.py"],
        modules=["mod_z"],
        symbols=["sym_a"],
    )
    assert scope_a.conflicts_with(scope_e) is True

    # Empty scopes -> no conflict
    empty_1 = ProposalScope()
    empty_2 = ProposalScope()
    assert empty_1.conflicts_with(empty_2) is False




# ID: 460e3938-324f-458f-b395-5b6679883215
def test_ProposalScope():
    scope_a = ProposalScope(
        files=["src/a.py", "src/b.py"],
        modules=["will.autonomy"],
        symbols=["func_a"],
        policies=["P1"],
    )
    scope_b = ProposalScope(
        files=["src/c.py"],
        modules=["will.autonomy"],
        symbols=["func_b"],
    )
    scope_c = ProposalScope(
        files=["src/x.py"],
        modules=["will.other"],
        symbols=["func_x"],
    )

    # Defaults are empty
    empty = ProposalScope()
    assert empty.files == []
    assert empty.modules == []
    assert empty.symbols == []
    assert empty.policies == []

    # No overlap -> no conflict
    assert scope_a.conflicts_with(scope_c) is False
    assert scope_c.conflicts_with(scope_a) is False

    # Shared module -> conflict
    assert scope_a.conflicts_with(scope_b) is True
    assert scope_b.conflicts_with(scope_a) is True

    # File-only overlap
    same_file = ProposalScope(files=["src/a.py"])
    assert scope_a.conflicts_with(same_file) is True

    # Symbol-only overlap
    same_symbol = ProposalScope(symbols=["func_a"])
    assert scope_a.conflicts_with(same_symbol) is True

    # A scope does not conflict with itself? It does (sets overlap).
    assert scope_a.conflicts_with(scope_a) is True

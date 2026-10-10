"""Proposal.check_submission and fail-closed risk for unknown actions.

Before this change the /proposals create path never validated, and
compute_risk skipped any action the registry did not know — so a proposal
of only unknown actions (or none) scored "safe", approval not required,
and was persisted. Submission and execution are now two checks: a proposal
awaiting approval is a valid submission; only execution needs approval.
"""

from __future__ import annotations

# body.atomic must finish loading before will.autonomy.proposal pulls in its
# registry imports (pre-existing circular import under isolated collection).
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalProvenance,
    ProposalScope,
    RiskAssessment,
)
from will.autonomy.proposal_mapper import ProposalMapper


def _provenance(**overrides: object) -> ProposalProvenance:
    fields: dict = {
        "anchor_kind": "issue",
        "anchor_refs": ["#1"],
        "problem_owner": "governor",
        "producer": "claude-session:core-darek",
    }
    fields.update(overrides)
    return ProposalProvenance(**fields)


def _proposal(*actions: ProposalAction, files: list[str] | None = None) -> Proposal:
    return Proposal(
        goal="g",
        actions=list(actions),
        scope=ProposalScope(files=["src/x.py"] if files is None else files),
        provenance=_provenance(),
    )


# ID: 03ac3a55-c693-47fe-8575-bd000d80911b
def test_unknown_action_is_never_scored_safe() -> None:
    proposal = _proposal(ProposalAction(action_id="no.such.action", order=0))
    proposal.compute_risk()

    assert proposal.risk is not None
    assert proposal.risk.overall_risk == "moderate"
    assert proposal.approval_required is True


# ID: f87e6fce-eab6-451d-86cd-63c3c089d069
def test_submission_refuses_unknown_and_missing_actions() -> None:
    unknown = _proposal(ProposalAction(action_id="no.such.action", order=0))
    assert any("not found in registry" in e for e in unknown.check_submission())

    empty = _proposal()
    assert "Proposal must have at least one action" in empty.check_submission()


# ID: d664a8c0-1280-44a6-a93c-d164a186db37
def test_submission_accepts_a_known_action() -> None:
    proposal = _proposal(ProposalAction(action_id="fix.format", order=0))
    assert proposal.check_submission() == []


# ID: 34749fd8-d74c-4132-9a37-08aada0775c5
def test_high_risk_awaiting_approval_is_a_valid_submission() -> None:
    """Submission must not demand the approval execution needs."""
    proposal = _proposal(ProposalAction(action_id="fix.format", order=0))
    proposal.risk = RiskAssessment(
        overall_risk="high", action_risks={}, risk_factors=[], mitigation=[]
    )

    assert proposal.check_submission() == []
    _, errors = proposal.validate()
    assert "High-risk proposals require approval" in errors


# ── ADR-168 Amendment 2026-10-10 A2: provenance ─────────────────────────────


# ID: a072f7c8-a641-4f18-b8fa-38b4ed9c9bba
def test_submission_refuses_a_proposal_without_provenance() -> None:
    proposal = _proposal(ProposalAction(action_id="fix.format", order=0))
    proposal.provenance = None

    errors = proposal.check_submission()

    assert any("provenance" in e for e in errors)


# ID: ae4c874e-c538-40a0-b06c-26e3e55133ae
def test_provenance_refuses_unknown_kind_owner_and_empty_fields() -> None:
    problems = _provenance(
        anchor_kind="vibe", anchor_refs=[" "], problem_owner="nobody", producer=""
    ).problems()

    assert len(problems) == 4


# ID: 956f1f7e-9f09-4deb-b935-e9493cf2a705
def test_finding_is_cores_problem_and_a_governor_request_is_the_governors() -> None:
    assert _provenance(anchor_kind="finding", problem_owner="governor").problems()
    assert _provenance(anchor_kind="finding", problem_owner="core").problems() == []
    assert _provenance(anchor_kind="governor_request", problem_owner="core").problems()
    assert (
        _provenance(
            anchor_kind="governor_request",
            anchor_refs=["add a status line to the daily report"],
        ).problems()
        == []
    )


# ID: 971533c3-c039-465b-a8c4-08addcad253a
def test_provenance_survives_storage_beside_existing_constraints() -> None:
    """Stored under constitutional_constraints; existing keys are kept."""
    proposal = _proposal(ProposalAction(action_id="fix.format", order=0))
    proposal.provenance = _provenance(retires=["src/old.py"])
    proposal.constitutional_constraints = {"finding_ids": ["f1"]}

    stored = ProposalMapper.to_db_model(proposal, dict)
    assert stored["constitutional_constraints"]["finding_ids"] == ["f1"]
    assert stored["constitutional_constraints"]["provenance"]["retires"] == [
        "src/old.py"
    ]

    restored = Proposal.from_dict(proposal.to_dict())
    assert restored.provenance == proposal.provenance
    assert restored.constitutional_constraints["finding_ids"] == ["f1"]


# ID: c0ece54a-c103-40eb-a35e-c67a37708284
def test_a_row_stored_before_provenance_existed_loads_without_it() -> None:
    proposal = _proposal(ProposalAction(action_id="fix.format", order=0))
    proposal.provenance = None

    assert Proposal.from_dict(proposal.to_dict()).provenance is None

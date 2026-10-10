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
    ProposalScope,
    RiskAssessment,
)


def _proposal(*actions: ProposalAction, files: list[str] | None = None) -> Proposal:
    return Proposal(
        goal="g",
        actions=list(actions),
        scope=ProposalScope(files=["src/x.py"] if files is None else files),
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

"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/validator_service.py
- Symbol: GovernanceDecision
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:25:06
"""

import pytest
from mind.governance.validator_service import GovernanceDecision
# Detected return type: GovernanceDecision is a dataclass/class, not a function. Tests will verify attribute values.

def test_governance_decision_initialization():
    """Test basic initialization with all attributes."""
    decision = GovernanceDecision(
        allowed=True,
        risk_tier="LOW",  # Assuming RiskTier can be string-constructed or is an enum
        approval_type="AUTO",  # Assuming ApprovalType can be string-constructed or is an enum
        rationale="All checks passed.",
        violations=[]
    )
    assert decision.allowed == True
    assert decision.risk_tier == "LOW"
    assert decision.approval_type == "AUTO"
    assert decision.rationale == "All checks passed."
    assert decision.violations == []

def test_governance_decision_with_violations():
    """Test initialization with a list of violations."""
    violations_list = ["Constraint A failed", "Constraint B failed"]
    decision = GovernanceDecision(
        allowed=False,
        risk_tier="HIGH",
        approval_type="MANUAL",
        rationale="Multiple violations found.",
        violations=violations_list
    )
    assert decision.allowed == False
    assert decision.risk_tier == "HIGH"
    assert decision.approval_type == "MANUAL"
    assert decision.rationale == "Multiple violations found."
    assert decision.violations == violations_list
    assert len(decision.violations) == 2

def test_governance_decision_default_rationale():
    """Test that rationale can be an empty string."""
    decision = GovernanceDecision(
        allowed=True,
        risk_tier="LOW",
        approval_type="AUTO",
        rationale="",
        violations=[]
    )
    assert decision.rationale == ""

def test_governance_decision_equality():
    """Test that two instances with same data are considered equal (if __eq__ is defined)."""
    decision1 = GovernanceDecision(
        allowed=False,
        risk_tier="MEDIUM",
        approval_type="MANUAL",
        rationale="Risk threshold exceeded.",
        violations=["Threshold check"]
    )
    decision2 = GovernanceDecision(
        allowed=False,
        risk_tier="MEDIUM",
        approval_type="MANUAL",
        rationale="Risk threshold exceeded.",
        violations=["Threshold check"]
    )
    # This test assumes the class has value-based equality (e.g., a dataclass).
    # If it's a regular class without __eq__, this will test object identity and likely fail.
    # We use '==' as required.
    assert decision1 == decision2

def test_governance_decision_inequality():
    """Test that different data leads to inequality."""
    decision1 = GovernanceDecision(
        allowed=True,
        risk_tier="LOW",
        approval_type="AUTO",
        rationale="OK",
        violations=[]
    )
    decision2 = GovernanceDecision(
        allowed=False,  # Different allowed
        risk_tier="LOW",
        approval_type="AUTO",
        rationale="OK",
        violations=[]
    )
    assert decision1 != decision2

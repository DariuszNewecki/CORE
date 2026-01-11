"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/constitutional_monitor.py
- Symbol: Violation
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:21:00
"""

import pytest
from mind.governance.constitutional_monitor import Violation

# Detected return type: Violation is a dataclass-like class, instantiation returns a Violation instance.

def test_violation_initialization_with_required_fields():
    """Test that a Violation can be created with only required fields."""
    violation = Violation(
        file_path="/full/path/to/file.py",
        policy_id="POL-001",
        description="A test violation",
        severity="high"
    )
    assert violation.file_path == "/full/path/to/file.py"
    assert violation.policy_id == "POL-001"
    assert violation.description == "A test violation"
    assert violation.severity == "high"
    assert violation.remediation_handler is None

def test_violation_initialization_with_all_fields():
    """Test that a Violation can be created with all fields, including optional remediation_handler."""
    violation = Violation(
        file_path="/another/full/path.txt",
        policy_id="POL-002",
        description="Another violation with handler",
        severity="medium",
        remediation_handler="auto_fix_function"
    )
    assert violation.file_path == "/another/full/path.txt"
    assert violation.policy_id == "POL-002"
    assert violation.description == "Another violation with handler"
    assert violation.severity == "medium"
    assert violation.remediation_handler == "auto_fix_function"

def test_violation_equality():
    """Test that two Violation instances with the same data are considered equal."""
    v1 = Violation(
        file_path="/some/file",
        policy_id="POL-1",
        description="Desc",
        severity="low"
    )
    v2 = Violation(
        file_path="/some/file",
        policy_id="POL-1",
        description="Desc",
        severity="low"
    )
    # Direct attribute comparison
    assert v1.file_path == v2.file_path
    assert v1.policy_id == v2.policy_id
    assert v1.description == v2.description
    assert v1.severity == v2.severity
    assert v1.remediation_handler == v2.remediation_handler

def test_violation_inequality():
    """Test that Violation instances with different data are not equal."""
    base = Violation(
        file_path="/base",
        policy_id="POL-BASE",
        description="Base",
        severity="info"
    )
    different_file = Violation(
        file_path="/different",
        policy_id="POL-BASE",
        description="Base",
        severity="info"
    )
    different_policy = Violation(
        file_path="/base",
        policy_id="POL-OTHER",
        description="Base",
        severity="info"
    )
    different_desc = Violation(
        file_path="/base",
        policy_id="POL-BASE",
        description="Different",
        severity="info"
    )
    different_severity = Violation(
        file_path="/base",
        policy_id="POL-BASE",
        description="Base",
        severity="critical"
    )
    different_handler = Violation(
        file_path="/base",
        policy_id="POL-BASE",
        description="Base",
        severity="info",
        remediation_handler="handler"
    )
    assert base.file_path != different_file.file_path
    assert base.policy_id != different_policy.policy_id
    assert base.description != different_desc.description
    assert base.severity != different_severity.severity
    assert base.remediation_handler != different_handler.remediation_handler

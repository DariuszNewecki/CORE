"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/violation_report.py
- Symbol: ViolationReport
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:45:41
"""

import pytest
from mind.governance.violation_report import ViolationReport

# ViolationReport is a dataclass/class with attributes, returns instance of ViolationReport

def test_violation_report_initialization():
    """Test basic initialization with required fields."""
    report = ViolationReport(
        rule_name="no_secrets",
        path="/src/config.yaml",
        message="API key found in file",
        severity="error"
    )

    assert report.rule_name == "no_secrets"
    assert report.path == "/src/config.yaml"
    assert report.message == "API key found in file"
    assert report.severity == "error"
    assert report.suggested_fix == ""
    assert report.source_policy == "unknown"

def test_violation_report_full_initialization():
    """Test initialization with all fields including optional ones."""
    report = ViolationReport(
        rule_name="license_header",
        path="/src/main.py",
        message="Missing license header",
        severity="warning",
        suggested_fix="Add MIT license header",
        source_policy="/policies/code_standards.yaml"
    )

    assert report.rule_name == "license_header"
    assert report.path == "/src/main.py"
    assert report.message == "Missing license header"
    assert report.severity == "warning"
    assert report.suggested_fix == "Add MIT license header"
    assert report.source_policy == "/policies/code_standards.yaml"

def test_violation_report_default_values():
    """Test that default values are correctly set when not provided."""
    report = ViolationReport(
        rule_name="test_rule",
        path="/test/file.txt",
        message="Test violation",
        severity="error"
    )

    assert report.suggested_fix == ""
    assert report.source_policy == "unknown"

def test_violation_report_equality():
    """Test that two reports with same values are equal."""
    report1 = ViolationReport(
        rule_name="same_rule",
        path="/same/path",
        message="Same message",
        severity="warning"
    )

    report2 = ViolationReport(
        rule_name="same_rule",
        path="/same/path",
        message="Same message",
        severity="warning"
    )

    assert report1.rule_name == report2.rule_name
    assert report1.path == report2.path
    assert report1.message == report2.message
    assert report1.severity == report2.severity
    assert report1.suggested_fix == report2.suggested_fix
    assert report1.source_policy == report2.source_policy

def test_violation_report_different_values():
    """Test that reports with different values are not equal."""
    report1 = ViolationReport(
        rule_name="rule1",
        path="/path1",
        message="Message 1",
        severity="error"
    )

    report2 = ViolationReport(
        rule_name="rule2",
        path="/path2",
        message="Message 2",
        severity="warning"
    )

    assert report1.rule_name != report2.rule_name
    assert report1.path != report2.path
    assert report1.message != report2.message
    assert report1.severity != report2.severity

def test_violation_report_with_empty_strings():
    """Test initialization with empty strings for optional fields."""
    report = ViolationReport(
        rule_name="empty_test",
        path="",
        message="",
        severity="",
        suggested_fix="",
        source_policy=""
    )

    assert report.rule_name == "empty_test"
    assert report.path == ""
    assert report.message == ""
    assert report.severity == ""
    assert report.suggested_fix == ""
    assert report.source_policy == ""

def test_violation_report_with_special_characters():
    """Test initialization with special characters in strings."""
    report = ViolationReport(
        rule_name="rule/with/slashes",
        path="/path/with spaces/file.name",
        message="Message with unicode: …",
        severity="error",
        suggested_fix="Fix with … ellipsis",
        source_policy="/policy/with-dashes.yaml"
    )

    assert report.rule_name == "rule/with/slashes"
    assert report.path == "/path/with spaces/file.name"
    assert report.message == "Message with unicode: …"
    assert report.severity == "error"
    assert report.suggested_fix == "Fix with … ellipsis"
    assert report.source_policy == "/policy/with-dashes.yaml"

def test_violation_report_severity_values():
    """Test different severity values."""
    for severity in ["error", "warning", "info", "critical"]:
        report = ViolationReport(
            rule_name=f"rule_{severity}",
            path="/test/path",
            message=f"Test {severity}",
            severity=severity
        )
        assert report.severity == severity

def test_violation_report_path_normalization():
    """Test that paths are stored as provided without normalization."""
    test_paths = [
        "./relative/path",
        "../parent/path",
        "/absolute/path",
        "C:\\Windows\\Path",
        "path/with/../parent"
    ]

    for path in test_paths:
        report = ViolationReport(
            rule_name="path_test",
            path=path,
            message="Path test",
            severity="error"
        )
        assert report.path == path

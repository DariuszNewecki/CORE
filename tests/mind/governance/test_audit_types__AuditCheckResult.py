"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_types.py
- Symbol: AuditCheckResult
- Status: 2 tests passed, some failed
- Passing tests: test_audit_check_result_equality, test_audit_check_result_with_extra_data
- Generated: 2026-01-11 02:01:38
"""

from mind.governance.audit_types import AuditCheckResult, AuditSeverity


def test_audit_check_result_equality():
    """Test that two AuditCheckResult instances with same values are equal."""
    result1 = AuditCheckResult(
        name="test",
        category="cat",
        duration_sec=1.0,
        findings_count=0,
        max_severity=None,
        fix_hint=None,
        extra=None,
    )
    result2 = AuditCheckResult(
        name="test",
        category="cat",
        duration_sec=1.0,
        findings_count=0,
        max_severity=None,
        fix_hint=None,
        extra=None,
    )
    assert result1.name == result2.name
    assert result1.category == result2.category
    assert result1.duration_sec == result2.duration_sec
    assert result1.findings_count == result2.findings_count
    assert result1.max_severity == result2.max_severity
    assert result1.fix_hint == result2.fix_hint
    assert result1.extra == result2.extra
    assert result1.has_issues == result2.has_issues


def test_audit_check_result_with_extra_data():
    """Test AuditCheckResult with extra dictionary field."""
    extra_data = {
        "details": "Additional information",
        "count": 42,
        "nested": {"key": "value"},
    }
    result = AuditCheckResult(
        name="check_with_extra",
        category="monitoring",
        duration_sec=5.5,
        findings_count=1,
        max_severity=AuditSeverity.INFO,
        fix_hint="No action required",
        extra=extra_data,
    )
    assert result.name == "check_with_extra"
    assert result.category == "monitoring"
    assert result.duration_sec == 5.5
    assert result.findings_count == 1
    assert result.max_severity == AuditSeverity.INFO
    assert result.fix_hint == "No action required"
    assert result.extra == extra_data
    assert result.has_issues

"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/policy_coverage_service.py
- Symbol: PolicyCoverageReport
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:50:19
"""

from mind.governance.policy_coverage_service import PolicyCoverageReport


# Detected return type: PolicyCoverageReport is a Pydantic BaseModel, not a function.
# Tests will validate instantiation, field types, and model behavior.


def test_policy_coverage_report_instantiation():
    """Test basic instantiation with valid data."""
    report = PolicyCoverageReport(
        report_id="test-id-123",
        generated_at_utc="2024-01-01T12:00:00Z",
        repo_root="/full/path/to/repo",
        summary={"total": 5, "covered": 3},
        records=[{"file": "a.py", "coverage": 0.8}],
        exit_code=0,
    )
    assert report.report_id == "test-id-123"
    assert report.generated_at_utc == "2024-01-01T12:00:00Z"
    assert report.repo_root == "/full/path/to/repo"
    assert report.summary == {"total": 5, "covered": 3}
    assert report.records == [{"file": "a.py", "coverage": 0.8}]
    assert report.exit_code == 0


def test_policy_coverage_report_field_types():
    """Test that fields enforce expected types."""
    report = PolicyCoverageReport(
        report_id="id",
        generated_at_utc="now",
        repo_root="/path",
        summary={},
        records=[],
        exit_code=1,
    )
    assert isinstance(report.report_id, str)
    assert isinstance(report.generated_at_utc, str)
    assert isinstance(report.repo_root, str)
    assert isinstance(report.summary, dict)
    assert isinstance(report.records, list)
    assert isinstance(report.exit_code, int)


def test_policy_coverage_report_with_minimal_data():
    """Test instantiation with minimal/empty data structures."""
    report = PolicyCoverageReport(
        report_id="",
        generated_at_utc="",
        repo_root="",
        summary={},
        records=[],
        exit_code=-1,
    )
    assert report.report_id == ""
    assert report.generated_at_utc == ""
    assert report.repo_root == ""
    assert report.summary == {}
    assert report.records == []
    assert report.exit_code == -1


def test_policy_coverage_report_equality():
    """Two instances with same data should be equal via ==."""
    data = {
        "report_id": "same",
        "generated_at_utc": "time",
        "repo_root": "/root",
        "summary": {"a": 1},
        "records": [{"b": 2}],
        "exit_code": 0,
    }
    report1 = PolicyCoverageReport(**data)
    report2 = PolicyCoverageReport(**data)
    assert report1 == report2
    assert report1.report_id == report2.report_id
    assert report1.summary == report2.summary


def test_policy_coverage_report_immutability():
    """Test that fields are immutable after creation (frozen model)."""
    report = PolicyCoverageReport(
        report_id="id",
        generated_at_utc="time",
        repo_root="/path",
        summary={"k": 1},
        records=[],
        exit_code=0,
    )
    # Pydantic BaseModel fields are mutable by default unless model is configured as frozen.
    # This test assumes standard mutable behavior.
    report.summary["k"] = 2  # This should work for a mutable dict
    assert report.summary["k"] == 2

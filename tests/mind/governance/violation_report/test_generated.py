from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.governance.violation_report import extract_error_data


# ID: 326fa8cb-21e2-4353-a52f-3878105f9179
def test_extract_error_data():
    # Happy path 1: plain exception degrades to legacy flat shape
    plain = ValueError("boom")
    result = extract_error_data(plain)
    assert result == {"error": "boom"}

    # Happy path 2: extra kwargs merged for plain exception
    result_extra = extract_error_data(plain, file_path="target/rel")
    assert result_extra == {"error": "boom", "file_path": "target/rel"}

    # Happy path 3: ConstitutionalViolationError uses structured to_dict()
    structured = {
        "rule_name": "R1",
        "path": "a/b",
        "source_policy": "P",
        "violations": [],
    }
    mock_exc = MagicMock()
    with patch(
        "mind.governance.violation_report.ConstitutionalViolationError",
        new=type(mock_exc),
    ):
        mock_exc.to_dict.return_value = structured
        result_violation = extract_error_data(mock_exc, file_path="x")
        assert result_violation == {**structured, "file_path": "x"}
        mock_exc.to_dict.assert_called_once_with()

    # Caller keys override helper keys on conflict
    mock_exc2 = MagicMock()
    with patch(
        "mind.governance.violation_report.ConstitutionalViolationError",
        new=type(mock_exc2),
    ):
        mock_exc2.to_dict.return_value = {"rule_name": "R1", "path": "orig"}
        result_override = extract_error_data(mock_exc2, path="override")
        assert result_override == {"rule_name": "R1", "path": "override"}



from mind.governance.violation_report import ConstitutionalViolationError


# ID: 6c9c6f19-7ccf-499e-9497-cbb533acba25
def test_ConstitutionalViolationError_to_dict():
    violation = MagicMock()
    violation.rule_name = "no_print_in_prod"
    violation.path = "src/app.py"
    violation.severity = "error"
    violation.source_policy = "constitutional"
    violation.message = "print() is forbidden in production code"
    violation.suggested_fix = "Use logging instead of print()"

    error = ConstitutionalViolationError([violation])

    result = error.to_dict()

    assert result["blocked_by"] == "IntentGuard"
    assert result["violation_count"] == 1
    assert result["error"] == str(error)
    assert result["violations"] == [
        {
            "rule_name": "no_print_in_prod",
            "path": "src/app.py",
            "severity": "error",
            "source_policy": "constitutional",
            "message": "print() is forbidden in production code",
            "suggested_fix": "Use logging instead of print()",
        }
    ]

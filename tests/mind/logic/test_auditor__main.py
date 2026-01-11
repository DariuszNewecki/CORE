"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/auditor.py
- Symbol: main
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:15:19
"""

import logging

from mind.logic.auditor import main


# Detected return type: main returns int (0 for success, 1 for violations)


def test_main_no_violations(monkeypatch, tmp_path, caplog):
    """Test main returns 0 when auditor finds no violations."""
    caplog.set_level(logging.INFO)

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Sample content")

    # Mock auditor to return empty results
    class MockAuditor:
        def audit_file(self, path):
            return []

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    # Call main with file path
    result = main([str(test_file)])

    assert result == 0
    assert f"Auditing file: {test_file}" in caplog.text
    assert "✅ COMPLIANT: No constitutional violations found." in caplog.text


def test_main_with_violations(monkeypatch, tmp_path, caplog):
    """Test main returns 1 and logs violations when auditor finds issues."""
    caplog.set_level(logging.INFO)

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Sample content")

    # Mock auditor to return violation results
    class MockAuditor:
        def audit_file(self, path):
            return [
                {
                    "rule_id": "RULE_001",
                    "severity": "error",
                    "message": "Test violation message",
                    "violations": ["Violation detail 1", "Violation detail 2"],
                },
                {
                    "rule_id": "RULE_002",
                    "severity": "warning",
                    "message": "Another violation",
                    "violations": [],
                },
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    # Call main with file path
    result = main([str(test_file)])

    assert result == 1
    assert f"Auditing file: {test_file}" in caplog.text
    assert "❌ NON-COMPLIANT: Found 2 violations." in caplog.text
    assert "[RULE_001] (ERROR)" in caplog.text
    assert "Issue:     Test violation message" in caplog.text
    assert "- Violation detail 1" in caplog.text
    assert "- Violation detail 2" in caplog.text
    assert "[RULE_002] (WARNING)" in caplog.text
    assert "Issue:     Another violation" in caplog.text


def test_main_missing_rule_id(monkeypatch, tmp_path, caplog):
    """Test main handles results with missing rule_id."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [
                {
                    "severity": "error",
                    "message": "Missing rule ID",
                    "violations": ["detail"],
                }
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "[<unknown>] (ERROR)" in caplog.text
    assert "Issue:     Missing rule ID" in caplog.text


def test_main_missing_severity(monkeypatch, tmp_path, caplog):
    """Test main handles results with missing severity."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [
                {"rule_id": "RULE_003", "message": "Missing severity", "violations": []}
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "[RULE_003] (ERROR)" in caplog.text  # Defaults to "error" uppercase


def test_main_missing_message(monkeypatch, tmp_path, caplog):
    """Test main handles results with missing message."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [{"rule_id": "RULE_004", "severity": "warning", "violations": []}]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "[RULE_004] (WARNING)" in caplog.text
    assert "Issue:     " in caplog.text  # Empty message


def test_main_none_violations(monkeypatch, tmp_path, caplog):
    """Test main handles results with None violations."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [
                {
                    "rule_id": "RULE_005",
                    "severity": "error",
                    "message": "None violations",
                    "violations": None,
                }
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "[RULE_005] (ERROR)" in caplog.text
    assert "Issue:     None violations" in caplog.text
    # Should not crash when violations is None


def test_main_empty_violations_list(monkeypatch, tmp_path, caplog):
    """Test main handles results with empty violations list."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [
                {
                    "rule_id": "RULE_006",
                    "severity": "info",
                    "message": "Empty violations",
                    "violations": [],
                }
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "[RULE_006] (INFO)" in caplog.text
    assert "Issue:     Empty violations" in caplog.text
    # Should not print any violation items


def test_main_default_argv(monkeypatch, tmp_path):
    """Test main uses sys.argv when argv is None."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return []

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    # Test with explicit None (should use sys.argv)
    # We'll patch sys.argv instead
    import sys

    original_argv = sys.argv
    sys.argv = ["prog", str(test_file)]

    try:
        result = main(None)
        assert result == 0
    finally:
        sys.argv = original_argv


def test_main_multiple_violation_details(monkeypatch, tmp_path, caplog):
    """Test main correctly formats multiple violation details."""
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    class MockAuditor:
        def audit_file(self, path):
            return [
                {
                    "rule_id": "RULE_007",
                    "severity": "error",
                    "message": "Multiple details",
                    "violations": ["First", "Second", "Third"],
                }
            ]

    monkeypatch.setattr("mind.logic.auditor.ConstitutionalAuditor", MockAuditor)

    result = main([str(test_file)])

    assert result == 1
    assert "- First" in caplog.text
    assert "- Second" in caplog.text
    assert "- Third" in caplog.text
    assert "-" * 40 in caplog.text  # Separator line

"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/atomic_actions_evaluator.py
- Symbol: format_atomic_action_violations
- Status: 8 tests passed, some failed
- Passing tests: test_empty_violations_list, test_single_violation_basic, test_single_violation_verbose_with_fix, test_multiple_violations_same_file, test_multiple_violations_different_files, test_violation_without_line_number, test_verbose_false_hides_suggested_fix, test_mixed_severity_markers
- Generated: 2026-01-11 03:31:31
"""

from pathlib import Path

from body.evaluators.atomic_actions_evaluator import format_atomic_action_violations


class TestFormatAtomicActionViolations:

    def test_empty_violations_list(self):
        """Test with empty violations list returns success message."""
        result = format_atomic_action_violations([])
        expected = "✅ All atomic actions follow constitutional pattern!"
        assert result == expected

    def test_single_violation_basic(self):
        """Test formatting of a single violation without verbose mode."""
        violation = type(
            "Violation",
            (),
            {
                "file_path": Path("/test/file.py"),
                "severity": "error",
                "function_name": "test_function",
                "line_number": 42,
                "rule_id": "RULE_001",
                "message": "Violation message here",
                "suggested_fix": None,
            },
        )()
        result = format_atomic_action_violations([violation], verbose=False)
        assert "❌ Found Atomic Action Violations:" in result
        assert "📄 /test/file.py" in result
        assert "🔴 test_function (line 42)" in result
        assert "Rule: RULE_001" in result
        assert "Violation message here" in result
        assert "💡 Fix:" not in result

    def test_single_violation_verbose_with_fix(self):
        """Test formatting with verbose mode showing suggested fix."""
        violation = type(
            "Violation",
            (),
            {
                "file_path": Path("/test/file.py"),
                "severity": "warning",
                "function_name": "test_function",
                "line_number": 42,
                "rule_id": "RULE_002",
                "message": "Warning message",
                "suggested_fix": "Use alternative approach",
            },
        )()
        result = format_atomic_action_violations([violation], verbose=True)
        assert "🟡 test_function (line 42)" in result
        assert "Rule: RULE_002" in result
        assert "Warning message" in result
        assert "💡 Fix: Use alternative approach" in result

    def test_multiple_violations_same_file(self):
        """Test formatting multiple violations in the same file."""
        violations = [
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/file.py"),
                    "severity": "error",
                    "function_name": "func1",
                    "line_number": 10,
                    "rule_id": "RULE_001",
                    "message": "First violation",
                    "suggested_fix": None,
                },
            )(),
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/file.py"),
                    "severity": "warning",
                    "function_name": "func2",
                    "line_number": 20,
                    "rule_id": "RULE_002",
                    "message": "Second violation",
                    "suggested_fix": None,
                },
            )(),
        ]
        result = format_atomic_action_violations(violations, verbose=False)
        assert result.count("📄 /test/file.py") == 1
        assert "🔴 func1 (line 10)" in result
        assert "🟡 func2 (line 20)" in result
        assert "Rule: RULE_001" in result
        assert "Rule: RULE_002" in result

    def test_multiple_violations_different_files(self):
        """Test formatting violations across different files."""
        violations = [
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/b.py"),
                    "severity": "error",
                    "function_name": "func_b",
                    "line_number": 5,
                    "rule_id": "RULE_001",
                    "message": "B file violation",
                    "suggested_fix": None,
                },
            )(),
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/a.py"),
                    "severity": "warning",
                    "function_name": "func_a",
                    "line_number": 15,
                    "rule_id": "RULE_002",
                    "message": "A file violation",
                    "suggested_fix": None,
                },
            )(),
        ]
        result = format_atomic_action_violations(violations, verbose=False)
        file_sections = result.split("📄")
        assert "/test/a.py" in file_sections[1]
        assert "/test/b.py" in file_sections[2]

    def test_violation_without_line_number(self):
        """Test formatting when line_number is None."""
        violation = type(
            "Violation",
            (),
            {
                "file_path": Path("/test/file.py"),
                "severity": "error",
                "function_name": "test_function",
                "line_number": None,
                "rule_id": "RULE_001",
                "message": "No line number",
                "suggested_fix": None,
            },
        )()
        result = format_atomic_action_violations([violation], verbose=False)
        assert "test_function (line ?)" in result

    def test_verbose_false_hides_suggested_fix(self):
        """Test that suggested_fix is hidden when verbose=False."""
        violation = type(
            "Violation",
            (),
            {
                "file_path": Path("/test/file.py"),
                "severity": "error",
                "function_name": "test_function",
                "line_number": 42,
                "rule_id": "RULE_001",
                "message": "Test message",
                "suggested_fix": "This should not appear",
            },
        )()
        result = format_atomic_action_violations([violation], verbose=False)
        assert "💡 Fix:" not in result
        assert "This should not appear" not in result

    def test_mixed_severity_markers(self):
        """Test correct severity markers for error vs warning."""
        violations = [
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/file.py"),
                    "severity": "error",
                    "function_name": "error_func",
                    "line_number": 1,
                    "rule_id": "RULE_001",
                    "message": "Error",
                    "suggested_fix": None,
                },
            )(),
            type(
                "Violation",
                (),
                {
                    "file_path": Path("/test/file.py"),
                    "severity": "warning",
                    "function_name": "warning_func",
                    "line_number": 2,
                    "rule_id": "RULE_002",
                    "message": "Warning",
                    "suggested_fix": None,
                },
            )(),
        ]
        result = format_atomic_action_violations(violations, verbose=False)
        assert "🔴 error_func" in result
        assert "🟡 warning_func" in result

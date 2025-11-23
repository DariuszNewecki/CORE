# tests/services/validation/test_syntax_checker.py
"""Tests for syntax_checker module."""

from __future__ import annotations

from services.validation.syntax_checker import check_syntax


class TestCheckSyntax:
    """Tests for check_syntax function."""

    def test_valid_python_code(self):
        """Test that valid Python code passes syntax check."""
        code = "def hello():\n    return 'world'"
        violations = check_syntax("test.py", code)
        assert violations == []

    def test_syntax_error_detected(self):
        """Test that syntax errors are detected."""
        code = "def hello(\n    return 'world'"
        violations = check_syntax("test.py", code)
        assert len(violations) == 1
        assert violations[0]["rule"] == "E999"
        assert violations[0]["severity"] == "error"
        assert "syntax" in violations[0]["message"].lower()

    def test_non_python_file_skipped(self):
        """Test that non-Python files are skipped."""
        code = "invalid python code"
        violations = check_syntax("test.txt", code)
        assert violations == []

    def test_empty_code(self):
        """Test that empty code is valid."""
        code = ""
        violations = check_syntax("test.py", code)
        assert violations == []

    def test_multiline_syntax_error(self):
        """Test syntax error with line number."""
        code = "x = 1\ny = 2\ndef broken(\n    pass"
        violations = check_syntax("test.py", code)
        assert len(violations) == 1
        assert violations[0]["line"] is not None

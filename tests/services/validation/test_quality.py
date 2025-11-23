# tests/services/validation/test_quality.py
"""Tests for quality module."""

from __future__ import annotations

from services.validation.quality import QualityChecker


class TestQualityChecker:
    """Tests for QualityChecker class."""

    def test_detects_todo_comment(self):
        """Test detection of TODO comments."""
        checker = QualityChecker()
        code = "# TODO: fix this later\ndef foo():\n    pass"
        violations = checker.check_for_todo_comments(code)
        assert len(violations) == 1
        assert violations[0]["rule"] == "clarity.no_todo_comments"
        assert violations[0]["severity"] == "warning"
        assert "TODO" in violations[0]["message"]

    def test_detects_fixme_comment(self):
        """Test detection of FIXME comments."""
        checker = QualityChecker()
        code = "def bar():\n    # FIXME: broken\n    return 42"
        violations = checker.check_for_todo_comments(code)
        assert len(violations) == 1
        assert "FIXME" in violations[0]["message"]

    def test_ignores_clean_code(self):
        """Test that clean code has no violations."""
        checker = QualityChecker()
        code = "def clean():\n    # Regular comment\n    return True"
        violations = checker.check_for_todo_comments(code)
        assert violations == []

    def test_detects_multiple_todos(self):
        """Test detection of multiple TODO/FIXME comments."""
        checker = QualityChecker()
        code = "# TODO: first\ndef foo():\n    # FIXME: second\n    # TODO: third\n    pass"
        violations = checker.check_for_todo_comments(code)
        assert len(violations) == 3

    def test_line_numbers_correct(self):
        """Test that line numbers are reported correctly."""
        checker = QualityChecker()
        code = "x = 1\ny = 2\n# TODO: fix\nz = 3"
        violations = checker.check_for_todo_comments(code)
        assert len(violations) == 1
        assert violations[0]["line"] == 3

    def test_empty_code(self):
        """Test that empty code has no violations."""
        checker = QualityChecker()
        violations = checker.check_for_todo_comments("")
        assert violations == []

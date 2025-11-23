# tests/services/validation/test_black_formatter.py
"""Tests for black_formatter module."""

from __future__ import annotations

import black
import pytest

from services.validation.black_formatter import format_code_with_black


class TestFormatCodeWithBlack:
    """Tests for format_code_with_black function."""

    def test_formats_simple_code(self):
        """Test that Black formats simple Python code."""
        code = "x=1+2"
        formatted = format_code_with_black(code)
        assert "x = 1 + 2" in formatted

    def test_formats_multiline_code(self):
        """Test formatting of multiline code."""
        code = "def hello(  ):\n    return   'world'"
        formatted = format_code_with_black(code)
        assert "def hello():" in formatted
        assert '    return "world"' in formatted

    def test_preserves_correct_formatting(self):
        """Test that already formatted code is unchanged."""
        code = 'def hello():\n    return "world"\n'
        formatted = format_code_with_black(code)
        assert formatted == code

    def test_raises_on_syntax_error(self):
        """Test that syntax errors raise black.InvalidInput."""
        code = "def broken(\n    pass"
        with pytest.raises(black.InvalidInput):
            format_code_with_black(code)

    def test_handles_empty_code(self):
        """Test formatting empty code."""
        code = ""
        formatted = format_code_with_black(code)
        assert formatted.strip() == ""

    def test_formats_imports(self):
        """Test that imports are formatted correctly."""
        code = "import os,sys"
        formatted = format_code_with_black(code)
        # Black won't split this into separate lines (needs isort for that)
        assert "import" in formatted

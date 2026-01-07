"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: ensure_trailing_newline
- Status: verified_in_sandbox
- Generated: 2026-01-07 22:13:08
"""

from shared.utils.common_knowledge import ensure_trailing_newline


# Detected return type: str
def test_ensure_trailing_newline_adds_newline_to_empty_string():
    result = ensure_trailing_newline("")
    assert result == "\n"


def test_ensure_trailing_newline_adds_newline_to_string_without_newline():
    result = ensure_trailing_newline("test string")
    assert result == "test string\n"


def test_ensure_trailing_newline_preserves_single_newline():
    result = ensure_trailing_newline("test string\n")
    assert result == "test string\n"


def test_ensure_trailing_newline_reduces_multiple_newlines_to_one():
    result = ensure_trailing_newline("test string\n\n\n")
    assert result == "test string\n"


def test_ensure_trailing_newline_handles_only_newlines():
    result = ensure_trailing_newline("\n\n\n")
    assert result == "\n"


def test_ensure_trailing_newline_strips_trailing_newlines_before_adding_one():
    result = ensure_trailing_newline("test\nstring\n\n")
    assert result == "test\nstring\n"


def test_ensure_trailing_newline_preserves_leading_newlines():
    result = ensure_trailing_newline("\n\ntest string")
    assert result == "\n\ntest string\n"


def test_ensure_trailing_newline_handles_string_with_spaces_and_newlines():
    result = ensure_trailing_newline("  test  \n  string  \n\n")
    assert result == "  test  \n  string  \n"


def test_ensure_trailing_newline_handles_unicode_ellipsis():
    result = ensure_trailing_newline("test…")
    assert result == "test…\n"


def test_ensure_trailing_newline_handles_unicode_ellipsis_with_newlines():
    result = ensure_trailing_newline("test…\n\n")
    assert result == "test…\n"

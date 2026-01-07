"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: normalize_whitespace
- Status: verified_in_sandbox
- Generated: 2026-01-07 22:12:16
"""

from shared.utils.common_knowledge import normalize_whitespace


# Detected return type: str


def test_normalize_whitespace_collapses_spaces():
    result = normalize_whitespace("hello    world")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_collapses_tabs():
    result = normalize_whitespace("hello\t\tworld")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_collapses_newlines():
    result = normalize_whitespace("hello\n\nworld")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_collapses_mixed_whitespace():
    result = normalize_whitespace("hello \t\n  world")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_trims_leading_trailing():
    result = normalize_whitespace("  hello world  ")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_empty_string():
    result = normalize_whitespace("")
    expected = ""
    assert result == expected


def test_normalize_whitespace_only_whitespace():
    result = normalize_whitespace("   \t\n  ")
    expected = ""
    assert result == expected


def test_normalize_whitespace_preserves_single_spaces():
    result = normalize_whitespace("hello world")
    expected = "hello world"
    assert result == expected


def test_normalize_whitespace_complex_string():
    result = normalize_whitespace("  This is\n\ta test\tstring.\n\n")
    expected = "This is a test string."
    assert result == expected

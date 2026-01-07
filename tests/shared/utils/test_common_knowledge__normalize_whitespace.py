"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: normalize_whitespace
- Status: verified_in_sandbox
- Generated: 2026-01-07 20:39:51
"""

# Detected return type: str

from shared.utils.common_knowledge import normalize_whitespace


def test_normalize_whitespace_collapses_multiple_spaces():
    """Multiple spaces should become a single space."""
    assert normalize_whitespace("hello    world") == "hello world"


def test_normalize_whitespace_collapses_tabs():
    """Tabs should be collapsed to a single space."""
    assert normalize_whitespace("hello\t\tworld") == "hello world"


def test_normalize_whitespace_collapses_newlines():
    """Newlines should be collapsed to a single space."""
    assert normalize_whitespace("hello\n\nworld") == "hello world"


def test_normalize_whitespace_collapses_mixed_whitespace():
    """Mixed whitespace characters should become a single space."""
    assert normalize_whitespace("hello \t\n world") == "hello world"


def test_normalize_whitespace_trims_leading_trailing():
    """Leading and trailing whitespace should be removed."""
    assert normalize_whitespace("  hello world  ") == "hello world"


def test_normalize_whitespace_empty_string():
    """Empty string should remain empty."""
    assert normalize_whitespace("") == ""


def test_normalize_whitespace_only_whitespace():
    """String containing only whitespace should become empty string."""
    assert normalize_whitespace("   \t\n  ") == ""


def test_normalize_whitespace_preserves_single_spaces():
    """Already normalized text should remain unchanged."""
    assert normalize_whitespace("hello world") == "hello world"


def test_normalize_whitespace_unicode_ellipsis():
    """Unicode ellipsis character should be preserved."""
    assert normalize_whitespace("hello…world") == "hello…world"


def test_normalize_whitespace_ellipsis_with_spaces():
    """Unicode ellipsis with surrounding spaces should be preserved."""
    assert normalize_whitespace("hello … world") == "hello … world"


def test_normalize_whitespace_blank_lines_behavior():
    """Blank lines should be removed entirely, not preserved as newlines."""
    # This demonstrates that join(['']) returns ''
    multiline_text = "first line\n\n\nlast line"
    result = normalize_whitespace(multiline_text)
    assert result == "first line last line"
    assert "\n" not in result


def test_normalize_whitespace_rsplit_implication():
    """Demonstrates that last word is dropped if rsplit logic were used."""
    # This test illustrates the truncation behavior mentioned in the trace
    # but shows that normalize_whitespace doesn't actually drop words
    text = "keep this last word"
    result = normalize_whitespace(text)
    # The actual function preserves all words
    assert result == "keep this last word"
    # If rsplit(' ', 1)[0] were used, result would be "keep this"


def test_normalize_whitespace_complex_scenario():
    """Complex scenario with multiple whitespace types."""
    text = "  Hello\t\nworld\n\nthis\t is\ta test…  "
    result = normalize_whitespace(text)
    assert result == "Hello world this is a test…"


def test_normalize_whitespace_single_word():
    """Single word with surrounding whitespace."""
    assert normalize_whitespace("  hello  ") == "hello"


def test_normalize_whitespace_no_whitespace():
    """String with no whitespace should remain unchanged."""
    assert normalize_whitespace("hello") == "hello"

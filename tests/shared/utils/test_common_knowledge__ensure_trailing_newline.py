"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: ensure_trailing_newline
- Status: verified_in_sandbox
- Generated: 2026-01-07 20:40:35
"""

# Detected return type: str

from shared.utils.common_knowledge import ensure_trailing_newline


def test_ensure_trailing_newline_empty_string():
    """Empty string should return just a newline."""
    result = ensure_trailing_newline("")
    assert result == "\n"


def test_ensure_trailing_newline_no_newline():
    """String without newline should get one appended."""
    result = ensure_trailing_newline("Hello world")
    assert result == "Hello world\n"


def test_ensure_trailing_newline_single_newline():
    """String already ending with one newline should be unchanged."""
    input_text = "Hello world\n"
    result = ensure_trailing_newline(input_text)
    assert result == input_text


def test_ensure_trailing_newline_multiple_newlines():
    """Multiple trailing newlines should be reduced to one."""
    result = ensure_trailing_newline("Hello world\n\n\n")
    assert result == "Hello world\n"


def test_ensure_trailing_newline_newlines_with_spaces():
    """rstrip only removes newlines, not other whitespace."""
    result = ensure_trailing_newline("Hello world  \n\n")
    assert result == "Hello world  \n"


def test_ensure_trailing_newline_only_newlines():
    """String consisting only of newlines should return single newline."""
    result = ensure_trailing_newline("\n\n\n")
    assert result == "\n"


def test_ensure_trailing_newline_with_unicode_ellipsis():
    """Unicode ellipsis character should be preserved correctly."""
    input_text = "Some text…\n\n"
    result = ensure_trailing_newline(input_text)
    assert result == "Some text…\n"


def test_ensure_trailing_newline_mixed_whitespace():
    """Tabs and spaces before newlines should not be stripped."""
    input_text = "Hello\t \n\n"
    result = ensure_trailing_newline(input_text)
    assert result == "Hello\t \n"


def test_ensure_trailing_newline_embedded_newlines():
    """Newlines in the middle of the string should be preserved."""
    input_text = "Line 1\nLine 2\nLine 3\n\n"
    result = ensure_trailing_newline(input_text)
    assert result == "Line 1\nLine 2\nLine 3\n"


def test_ensure_trailing_newline_carriage_return():
    """Carriage returns are not stripped, only newlines."""
    input_text = "Hello\r\n\n"
    result = ensure_trailing_newline(input_text)
    assert result == "Hello\r\n"

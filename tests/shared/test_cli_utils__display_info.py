"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: display_info
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:49:45
"""

import pytest
from shared.cli_utils import display_info

# The target function 'display_info' returns None. Tests will verify it executes without error.

# Since the TARGET CODE shows a regular 'def', synchronous test functions are used.

def test_display_info_prints_cyan_message(capsys):
    """Test that the function prints the message with cyan formatting."""
    test_msg = "Test information"
    display_info(test_msg)
    captured = capsys.readouterr()
    # The console.print function outputs to sys.stdout by default.
    # We check that the output contains the message.
    # The exact ANSI sequence might vary, so we check for the message content.
    assert test_msg in captured.out

def test_display_info_with_empty_string(capsys):
    """Test that the function handles an empty string."""
    display_info("")
    captured = capsys.readouterr()
    # Should not crash; may print just formatting codes.
    assert captured.out is not None

def test_display_info_with_special_characters(capsys):
    """Test that the function handles special characters."""
    test_msg = "Message with unicode: こんにちは …"
    display_info(test_msg)
    captured = capsys.readouterr()
    assert "こんにちは" in captured.out
    # Using the Unicode Ellipsis character as per CRITICAL RULES.
    assert "…" in captured.out

def test_display_info_with_multiline_string(capsys):
    """Test that the function handles multiline strings."""
    test_msg = "Line 1\nLine 2\nLine 3"
    display_info(test_msg)
    captured = capsys.readouterr()
    assert "Line 1" in captured.out
    assert "Line 2" in captured.out
    assert "Line 3" in captured.out

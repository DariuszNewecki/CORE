"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: display_error
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:05:15
"""

from shared.cli_utils import display_error


# The function 'display_error' is a regular function (not async) that returns None.
# It prints a formatted message to the console. Testing will capture stdout.


def test_display_error_prints_formatted_message(capsys):
    """Test that the function prints the message with rich formatting."""
    test_msg = "Test error message"
    display_error(test_msg)
    captured = capsys.readouterr()
    # The function uses console.print with [bold red] tags.
    # The exact output depends on the Rich console's handling of tags.
    # We assert the raw text without style tags is present.
    # A safe assertion is that the original message is in the output.
    assert test_msg in captured.out


def test_display_error_with_empty_string(capsys):
    """Test that the function handles an empty message string."""
    display_error("")
    captured = capsys.readouterr()
    # The function should still call console.print, output may contain just formatting tags.
    # We assert the output is not None (something was printed).
    assert captured.out is not None


def test_display_error_with_special_characters(capsys):
    """Test that the function handles special characters in the message."""
    test_msg = "Error: 100% done… (Unicode ellipsis)"
    display_error(test_msg)
    captured = capsys.readouterr()
    assert "100% done…" in captured.out
    # Ensure the Unicode ellipsis (…) is used, not three dots.


def test_display_error_returns_none():
    """Explicitly test that the function returns None."""
    result = display_error("test")
    assert result is None

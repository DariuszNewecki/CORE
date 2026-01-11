"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: display_error
- Status: 3 tests passed, some failed
- Passing tests: test_display_error_prints_formatted_message, test_display_error_with_empty_string, test_display_error_is_synchronous
- Generated: 2026-01-11 10:40:33
"""

import pytest
from shared.cli_utils import display_error

def test_display_error_prints_formatted_message(capsys):
    """Test that display_error prints the message with rich formatting."""
    test_msg = 'Test error message'
    display_error(test_msg)
    captured = capsys.readouterr()
    assert test_msg in captured.out

def test_display_error_with_empty_string(capsys):
    """Test display_error with an empty message string."""
    display_error('')
    captured = capsys.readouterr()
    assert captured.out is not None

def test_display_error_is_synchronous():
    """Confirm the function is not async by checking its type."""
    import inspect
    assert not inspect.iscoroutinefunction(display_error)

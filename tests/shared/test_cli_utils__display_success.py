"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: display_success
- Status: 4 tests passed, some failed
- Passing tests: test_display_success_basic_message, test_display_success_empty_string, test_display_success_special_characters, test_display_success_long_message
- Generated: 2026-01-11 00:05:24
"""

import pytest
from shared.cli_utils import display_success

def test_display_success_basic_message():
    """Test that display_success can be called with a basic string."""
    display_success('Operation completed successfully')

def test_display_success_empty_string():
    """Test display_success with empty string."""
    display_success('')

def test_display_success_special_characters():
    """Test display_success with special characters and Unicode."""
    display_success('Success with emoji 🎉 and symbols: @#$%')

def test_display_success_long_message():
    """Test display_success with a long message."""
    long_msg = 'This is a very long success message ' * 10
    display_success(long_msg)

"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: display_info
- Status: 1 tests passed, some failed
- Passing tests: test_display_info_returns_none
- Generated: 2026-01-11 00:05:50
"""

import pytest
from shared.cli_utils import display_info

def test_display_info_returns_none():
    """Test that display_info returns None."""
    result = display_info('test')
    assert result == None

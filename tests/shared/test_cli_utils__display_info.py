"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: display_info
- Status: 1 tests passed, some failed
- Passing tests: test_display_info_return_value
- Generated: 2026-01-11 10:41:22
"""

import pytest
from shared.cli_utils import display_info

def test_display_info_return_value():
    """Explicitly test that display_info returns None."""
    result = display_info('test')
    assert result is None

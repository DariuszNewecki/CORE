"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/time.py
- Symbol: now_iso
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:08:51
"""

import pytest
from shared.time import now_iso

# Detected return type: str (ISO 8601 formatted UTC timestamp string)

def test_now_iso_returns_string():
    """Test that now_iso returns a string."""
    result = now_iso()
    assert isinstance(result, str)

def test_now_iso_iso8601_format():
    """Test that the returned string conforms to ISO 8601 basic format."""
    result = now_iso()
    # Expected pattern: YYYY-MM-DDTHH:MM:SS.ssssss+00:00
    # Use regex to validate the structure.
    import re
    pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$'
    assert re.match(pattern, result) is not None

def test_now_iso_contains_utc_offset():
    """Test that the returned string ends with the UTC offset +00:00."""
    result = now_iso()
    assert result.endswith('+00:00')

def test_now_iso_contains_t_separator():
    """Test that the date and time are separated by 'T'."""
    result = now_iso()
    assert 'T' in result

def test_now_iso_microseconds_present():
    """Test that the time component includes microseconds."""
    result = now_iso()
    # Split at 'T' and then at '+'
    time_part = result.split('T')[1].split('+')[0]
    # Time part should be HH:MM:SS.ssssss
    assert '.' in time_part
    microseconds_part = time_part.split('.')[1]
    assert len(microseconds_part) == 6
    assert microseconds_part.isdigit()

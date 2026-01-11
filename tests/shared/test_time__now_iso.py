"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/time.py
- Symbol: now_iso
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:53:04
"""

import pytest
from shared.time import now_iso

# Detected return type: str (ISO 8601 formatted UTC timestamp)

def test_now_iso_returns_string():
    """Test that now_iso returns a string."""
    result = now_iso()
    assert isinstance(result, str), f"Expected str, got {type(result)}"

def test_now_iso_iso8601_format():
    """Test that the returned string follows ISO 8601 format."""
    result = now_iso()

    # ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ssssss+00:00 or Z
    # Since it's UTC, it should end with '+00:00' or 'Z'
    assert len(result) >= 20, f"String too short for ISO 8601: {result}"

    # Check for date part
    assert result[4] == '-', f"Missing dash after year: {result}"
    assert result[7] == '-', f"Missing dash after month: {result}"

    # Check for 'T' separator
    assert result[10] == 'T', f"Missing 'T' separator: {result}"

    # Check for time part separators
    assert result[13] == ':', f"Missing colon after hours: {result}"
    assert result[16] == ':', f"Missing colon after minutes: {result}"

    # Check UTC indicator (either ends with '+00:00' or 'Z')
    assert result.endswith('+00:00') or result.endswith('Z'), \
        f"Missing UTC timezone indicator: {result}"

def test_now_iso_contains_valid_date():
    """Test that the returned string contains valid date components."""
    result = now_iso()

    # Extract date parts
    year = int(result[0:4])
    month = int(result[5:7])
    day = int(result[8:10])

    # Basic validation of date ranges
    assert 2000 <= year <= 2100, f"Year out of reasonable range: {year}"
    assert 1 <= month <= 12, f"Month out of range: {month}"
    assert 1 <= day <= 31, f"Day out of range: {day}"

def test_now_iso_contains_valid_time():
    """Test that the returned string contains valid time components."""
    result = now_iso()

    # Find where time starts (after 'T')
    t_index = result.find('T')
    time_part = result[t_index + 1:]

    # Remove timezone suffix to get just the time
    if time_part.endswith('+00:00'):
        time_only = time_part[:-6]
    elif time_part.endswith('Z'):
        time_only = time_part[:-1]
    else:
        pytest.fail(f"Unexpected timezone format: {result}")

    # Extract time components
    hours = int(time_only[0:2])
    minutes = int(time_only[3:5])
    seconds = int(time_only[6:8]) if len(time_only) > 8 else 0

    # Basic validation of time ranges
    assert 0 <= hours <= 23, f"Hours out of range: {hours}"
    assert 0 <= minutes <= 59, f"Minutes out of range: {minutes}"
    assert 0 <= seconds <= 60, f"Seconds out of range: {seconds}"  # 60 for leap seconds

def test_now_iso_sequential_calls_different():
    """Test that sequential calls return different timestamps (at least microseconds differ)."""
    result1 = now_iso()
    result2 = now_iso()

    # They should not be identical (microseconds should differ)
    assert result1 != result2, \
        f"Sequential calls returned identical timestamps: {result1}"

def test_now_iso_utc_timezone():
    """Test that the timestamp explicitly indicates UTC timezone."""
    result = now_iso()

    # Should end with either '+00:00' or 'Z' for UTC
    assert result.endswith('+00:00') or result.endswith('Z'), \
        f"Timestamp does not indicate UTC: {result}"

    # If it ends with '+00:00', verify the format
    if result.endswith('+00:00'):
        # Check that it's exactly '+00:00'
        assert result[-6:] == '+00:00', f"Unexpected UTC offset: {result[-6:]}"

    # If it ends with 'Z', verify it's uppercase
    if result.endswith('Z'):
        assert result[-1] == 'Z', f"UTC 'Z' should be uppercase: {result[-1]}"

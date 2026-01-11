"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/main.py
- Symbol: health_check
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:44:38
"""

import pytest
from main import health_check

# Detected return type: dict (asynchronous function returning JSON-like status)

@pytest.mark.asyncio
async def test_health_check_returns_ok_status():
    """Test that health_check returns the correct status dictionary."""
    result = await health_check()
    expected = {"status": "ok"}
    assert result == expected

@pytest.mark.asyncio
async def test_health_check_returns_dict():
    """Test that health_check returns a dictionary."""
    result = await health_check()
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_health_check_dict_has_status_key():
    """Test that the returned dict contains the 'status' key."""
    result = await health_check()
    assert "status" in result

@pytest.mark.asyncio
async def test_health_check_status_value_is_ok():
    """Test that the 'status' key has the value 'ok'."""
    result = await health_check()
    assert result["status"] == "ok"

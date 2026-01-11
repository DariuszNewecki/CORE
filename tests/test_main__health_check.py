"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/main.py
- Symbol: health_check
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:35:26
"""

import pytest
from main import health_check

# Detected return type: dict (async function returning a JSON-like status dict)

@pytest.mark.asyncio
async def test_health_check_returns_ok_status():
    result = await health_check()
    assert result == {"status": "ok"}

@pytest.mark.asyncio
async def test_health_check_returns_dict():
    result = await health_check()
    assert isinstance(result, dict)
    assert "status" in result

@pytest.mark.asyncio
async def test_health_check_status_value_is_ok():
    result = await health_check()
    assert result["status"] == "ok"

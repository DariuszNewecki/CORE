"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_format_code
- Status: 6 tests passed, some failed
- Passing tests: test_action_format_code_basic, test_action_format_code_with_write, test_action_format_code_explicit_false, test_action_format_code_duration_calculation, test_action_format_code_always_true_formatted, test_action_format_code_format_code_called
- Generated: 2026-01-11 02:52:15
"""

from unittest.mock import patch

import pytest

from body.atomic.fix_actions import action_format_code
from shared.governance_token import authorize_execution


@pytest.mark.asyncio
async def test_action_format_code_basic():
    """Test basic formatting without writing."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [
                99.0,
                100.0,
                100.5,
            ]  # [0]: consumed by wrapper's logger.debug LogRecord; [1]: action start; [2]: action end
            with authorize_execution("format.code"):
                result = await action_format_code(write=False)
            mock_format.assert_called_once()
            assert result.action_id == "fix.format"
            assert result.ok
            assert result.data == {"formatted": True, "write": False}
            assert result.duration_sec == 0.5


@pytest.mark.asyncio
async def test_action_format_code_with_write():
    """Test formatting with write=True."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [199.0, 200.0, 200.75]
            with authorize_execution("format.code"):
                result = await action_format_code(write=True)
            mock_format.assert_called_once()
            assert result.action_id == "fix.format"
            assert result.ok
            assert result.data == {"formatted": True, "write": True}
            assert result.duration_sec == 0.75


@pytest.mark.asyncio
async def test_action_format_code_explicit_false():
    """Test with explicit write=False parameter."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [299.0, 300.0, 300.25]
            with authorize_execution("format.code"):
                result = await action_format_code(write=False)
            mock_format.assert_called_once()
            assert not result.data["write"]


@pytest.mark.asyncio
async def test_action_format_code_duration_calculation():
    """Verify duration calculation is correct."""
    with patch("body.self_healing.code_style_service.format_code"):
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [499.0, 500.0, 502.5]
            with authorize_execution("format.code"):
                result = await action_format_code(write=False)
            assert result.duration_sec == 2.5


@pytest.mark.asyncio
async def test_action_format_code_always_true_formatted():
    """Verify formatted is always True in data."""
    with patch("body.self_healing.code_style_service.format_code"):
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [-1.0, 0.0, 1.0]
            with authorize_execution("format.code"):
                result = await action_format_code(write=False)
            assert result.data["formatted"]


@pytest.mark.asyncio
async def test_action_format_code_format_code_called():
    """Verify format_code() is always called exactly once."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with patch("body.atomic.fix_actions.time.time") as mock_time:
            mock_time.side_effect = [-1.0, 0.0, 1.0]
            with authorize_execution("format.code"):
                await action_format_code(write=False)
            mock_format.assert_called_once_with(path=None, write=False)

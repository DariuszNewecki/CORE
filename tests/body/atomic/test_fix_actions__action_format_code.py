"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_format_code
- Status: 6 tests passed, some failed
- Passing tests: test_action_format_code_basic, test_action_format_code_with_write, test_action_format_code_explicit_false, test_action_format_code_duration_calculation, test_action_format_code_always_true_formatted, test_action_format_code_format_code_called
- Generated: 2026-01-11 02:52:15
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from body.atomic.fix_actions import action_format_code

@pytest.mark.asyncio
async def test_action_format_code_basic():
    """Test basic formatting without writing."""
    with patch('body.atomic.fix_actions.format_code') as mock_format:
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [100.0, 100.5]
            result = await action_format_code(write=False)
            mock_format.assert_called_once()
            assert result.action_id == 'fix.format'
            assert result.ok == True
            assert result.data == {'formatted': True, 'write': False}
            assert result.duration_sec == 0.5

@pytest.mark.asyncio
async def test_action_format_code_with_write():
    """Test formatting with write=True."""
    with patch('body.atomic.fix_actions.format_code') as mock_format:
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [200.0, 200.75]
            result = await action_format_code(write=True)
            mock_format.assert_called_once()
            assert result.action_id == 'fix.format'
            assert result.ok == True
            assert result.data == {'formatted': True, 'write': True}
            assert result.duration_sec == 0.75

@pytest.mark.asyncio
async def test_action_format_code_explicit_false():
    """Test with explicit write=False parameter."""
    with patch('body.atomic.fix_actions.format_code') as mock_format:
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [300.0, 300.25]
            result = await action_format_code(write=False)
            mock_format.assert_called_once()
            assert result.data['write'] == False

@pytest.mark.asyncio
async def test_action_format_code_duration_calculation():
    """Verify duration calculation is correct."""
    with patch('body.atomic.fix_actions.format_code'):
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [500.0, 502.5]
            result = await action_format_code(write=False)
            assert result.duration_sec == 2.5

@pytest.mark.asyncio
async def test_action_format_code_always_true_formatted():
    """Verify formatted is always True in data."""
    with patch('body.atomic.fix_actions.format_code'):
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [0.0, 1.0]
            result = await action_format_code(write=False)
            assert result.data['formatted'] == True

@pytest.mark.asyncio
async def test_action_format_code_format_code_called():
    """Verify format_code() is always called exactly once."""
    with patch('body.atomic.fix_actions.format_code') as mock_format:
        with patch('body.atomic.fix_actions.time.time') as mock_time:
            mock_time.side_effect = [0.0, 1.0]
            await action_format_code(write=False)
            mock_format.assert_called_once_with()

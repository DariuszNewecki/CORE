"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: async_command
- Status: 1 tests passed, some failed
- Passing tests: test_async_command_preserves_function_metadata
- Generated: 2026-01-11 00:06:11
"""

import pytest
from shared.cli_utils import async_command

@pytest.mark.asyncio
async def test_async_command_preserves_function_metadata():

    @async_command
    async def my_async_func(x: int) -> int:
        """Test docstring."""
        return x * 2
    assert my_async_func.__name__ == 'my_async_func'
    assert my_async_func.__doc__ == 'Test docstring.'

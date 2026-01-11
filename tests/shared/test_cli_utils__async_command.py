"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: async_command
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:50:25
"""

import pytest
from shared.cli_utils import async_command
import asyncio

# Detected return type: The decorator returns a synchronous wrapper function.
# The wrapper itself is not async; it runs the decorated async function via asyncio.run.

# Test that the decorated function correctly runs an async function and returns its result.
def test_async_command_runs_async_function():
    @async_command
    async def sample_coro():
        await asyncio.sleep(0)
        return "success"
    result = sample_coro()
    assert result == "success"

# Test that the wrapper raises RuntimeError when called inside a running event loop.
def test_async_command_raises_inside_running_loop():
    @async_command
    async def inner_coro():
        return "should not run"

    async def run_test():
        with pytest.raises(RuntimeError) as exc_info:
            inner_coro()
        assert "async_command cannot run inside an already-running event loop" in str(exc_info.value)

    asyncio.run(run_test())

# Test that the decorator preserves the original function's __name__.
def test_async_command_preserves_name():
    @async_command
    async def my_async_func():
        pass
    assert my_async_func.__name__ == "my_async_func"

# Test that arguments are passed correctly to the decorated async function.
def test_async_command_passes_args_kwargs():
    @async_command
    async def compute(a, b, *, multiplier=1):
        return (a + b) * multiplier
    result = compute(2, 3, multiplier=4)
    assert result == 20

# Test that the wrapper works when no running loop exists (normal case).
def test_async_command_no_running_loop():
    # Ensure no running loop in this thread
    try:
        asyncio.get_running_loop()
        pytest.skip("Test requires no running event loop")
    except RuntimeError:
        pass

    @async_command
    async def echo(x):
        return x
    result = echo("test")
    assert result == "test"

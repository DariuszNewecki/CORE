"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: async_command
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:42:36
"""

import pytest
from shared.cli_utils import async_command
import asyncio

# Detected: async_command is a decorator that returns a synchronous wrapper function
# The wrapper runs the decorated async function via asyncio.run()

# Test for the decorator's basic functionality
def test_async_command_decorator_returns_wrapper():
    """Test that async_command returns a callable wrapper."""

    @async_command
    async def sample_async_func():
        return "test_result"

    # The decorator should return a function (wrapper)
    assert callable(sample_async_func)

    # The wrapper should execute the async function and return its result
    result = sample_async_func()
    assert result == "test_result"

# Test for the RuntimeError when called from running event loop
def test_async_command_raises_runtime_error_in_running_loop():
    """Test that async_command raises RuntimeError when called from running event loop."""

    @async_command
    async def sample_async_func():
        return "should_not_execute"

    async def run_in_loop():
        # This should raise RuntimeError because we're in a running loop
        try:
            sample_async_func()
            return False  # Should not reach here
        except RuntimeError as e:
            error_msg = str(e)
            expected_msg = "async_command cannot run inside an already-running event loop"
            assert expected_msg in error_msg
            return True

    # Run the test in an event loop
    result = asyncio.run(run_in_loop())
    assert result == True

# Test that async_command works outside of running event loop
def test_async_command_works_without_running_loop():
    """Test that async_command works when no event loop is running."""

    @async_command
    async def sample_async_func(x, y):
        return x + y

    # Should work fine outside of running event loop
    result = sample_async_func(5, 3)
    assert result == 8

# Test with async function that raises exception
def test_async_command_propagates_exceptions():
    """Test that exceptions from async function are propagated."""

    @async_command
    async def failing_async_func():
        raise ValueError("Test error")

    try:
        failing_async_func()
        assert False  # Should not reach here
    except ValueError as e:
        assert str(e) == "Test error"

# Test with async function that has no return value
def test_async_command_with_no_return():
    """Test async_command with async function that returns None."""

    test_state = {"executed": False}

    @async_command
    async def no_return_func():
        test_state["executed"] = True

    result = no_return_func()
    assert result is None
    assert test_state["executed"] == True

# Test with async function that accepts arguments
def test_async_command_with_arguments():
    """Test async_command with async function that accepts various arguments."""

    @async_command
    async def complex_async_func(a, b=10, *, c=20):
        return a + b + c

    # Test with positional arguments
    result1 = complex_async_func(5)
    assert result1 == 35  # 5 + 10 + 20

    # Test with keyword arguments
    result2 = complex_async_func(5, b=15, c=25)
    assert result2 == 45  # 5 + 15 + 25

# Test that wrapper preserves function metadata
def test_async_command_preserves_metadata():
    """Test that functools.wraps preserves function metadata."""

    @async_command
    async def documented_func():
        """This is a test function."""
        return 42

    # Check that name is preserved
    assert documented_func.__name__ == "documented_func"

    # Check that docstring is preserved
    assert documented_func.__doc__ == "This is a test function."

# Test nested async operations
def test_async_command_with_nested_async_operations():
    """Test async_command with async function that does nested async operations."""

    @async_command
    async def nested_async_func():
        # Simulate some async work
        await asyncio.sleep(0)
        return "done"

    result = nested_async_func()
    assert result == "done"

# Test with multiple decorated functions
def test_async_command_multiple_functions():
    """Test that async_command works correctly with multiple decorated functions."""

    @async_command
    async def func1():
        return "first"

    @async_command
    async def func2():
        return "second"

    assert func1() == "first"
    assert func2() == "second"

# Test that decorator doesn't execute function immediately
def test_async_command_deferred_execution():
    """Test that decorator doesn't execute the function immediately."""

    execution_count = 0

    @async_command
    async def counting_func():
        nonlocal execution_count
        execution_count += 1
        return execution_count

    # Function should not have been executed yet
    assert execution_count == 0

    # Execute once
    result1 = counting_func()
    assert result1 == 1
    assert execution_count == 1

    # Execute again
    result2 = counting_func()
    assert result2 == 2
    assert execution_count == 2

"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: core_command
- Status: 12 tests passed, some failed
- Passing tests: test_core_command_registers_metadata, test_core_command_sync_function_no_context, test_core_command_requires_context_missing, test_core_command_dangerous_with_write_no_confirmation, test_core_command_dangerous_with_confirmation_cancelled, test_core_command_dangerous_with_confirmation_accepted, test_core_command_running_inside_existing_loop, test_core_command_action_result_failure_exits, test_core_command_non_none_result_printed, test_core_command_none_result_not_printed, test_core_command_exception_handling, test_core_command_dispose_engine_called
- Generated: 2026-01-11 00:05:04
"""

import pytest
from shared.cli_utils import core_command
import asyncio
import typer
from unittest.mock import Mock, patch
from typing import Any

def test_core_command_registers_metadata():
    """Test that the decorator registers command metadata."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def test_func():
        return 'test'
    from shared.cli_utils import COMMAND_REGISTRY
    assert 'test_func' in COMMAND_REGISTRY
    metadata = COMMAND_REGISTRY['test_func']
    assert metadata.dangerous == True
    assert metadata.confirmation == False
    assert metadata.requires_context == False

def test_core_command_sync_function_no_context():
    """Test sync function without context requirement."""

    @core_command(requires_context=False)
    def sync_func():
        return 'sync_result'
    result = sync_func()
    assert result == 'sync_result'

def test_core_command_requires_context_missing():
    """Test that missing context raises error when required."""

    @core_command(requires_context=True)
    def func_with_context(ctx: typer.Context):
        return 'should_not_reach'
    with patch('shared.cli_utils.console.print') as mock_print:
        with pytest.raises(typer.Exit) as exc_info:
            func_with_context()
        assert exc_info.value.exit_code == 1
        assert mock_print.called
        call_args = mock_print.call_args[0][0]
        assert "System Error: CLI command must accept 'ctx: typer.Context'" in call_args

def test_core_command_dangerous_with_write_no_confirmation():
    """Test dangerous command with --write but no confirmation required."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def dangerous_func(write: bool=False):
        return f'executed with write={write}'
    result = dangerous_func(write=True)
    assert result == 'executed with write=True'

def test_core_command_dangerous_with_confirmation_cancelled():
    """Test dangerous command with confirmation that gets cancelled."""

    @core_command(dangerous=True, confirmation=True, requires_context=False)
    def dangerous_func(write: bool=False):
        return 'should_not_reach'
    with patch('shared.cli_utils.confirm_action', return_value=False):
        with pytest.raises(typer.Exit) as exc_info:
            dangerous_func(write=True)
        assert exc_info.value.exit_code == 0

def test_core_command_dangerous_with_confirmation_accepted():
    """Test dangerous command with confirmation that gets accepted."""

    @core_command(dangerous=True, confirmation=True, requires_context=False)
    def dangerous_func(write: bool=False):
        return 'executed'
    with patch('shared.cli_utils.confirm_action', return_value=True):
        result = dangerous_func(write=True)
        assert result == 'executed'

def test_core_command_running_inside_existing_loop():
    """Test that command raises error when called inside running event loop."""

    @core_command(requires_context=False)
    def simple_func():
        return 'test'

    async def nested_call():
        return simple_func()
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(nested_call())
    assert 'cannot run inside an already-running event loop' in str(exc_info.value)

def test_core_command_action_result_failure_exits():
    """Test that non-ok ActionResult raises typer.Exit(1)."""
    from shared.cli_utils import ActionResult

    @core_command(requires_context=False)
    def failing_action():
        return ActionResult(ok=False, message='Failure', data={})
    with pytest.raises(typer.Exit) as exc_info:
        failing_action()
    assert exc_info.value.exit_code == 1

def test_core_command_non_none_result_printed():
    """Test that non-None, non-ActionResult results get printed."""

    @core_command(requires_context=False)
    def returning_func():
        return 'some output'
    with patch('shared.cli_utils.console.print') as mock_print:
        result = returning_func()
        assert result == 'some output'
        assert mock_print.called
        assert mock_print.call_args[0][0] == 'some output'

def test_core_command_none_result_not_printed():
    """Test that None result doesn't get printed."""

    @core_command(requires_context=False)
    def none_func():
        return None
    with patch('shared.cli_utils.console.print') as mock_print:
        result = none_func()
        assert result is None
        assert not mock_print.called

def test_core_command_exception_handling():
    """Test that exceptions are caught and result in typer.Exit(1)."""

    @core_command(requires_context=False)
    def failing_func():
        raise ValueError('Something went wrong')
    with patch('shared.cli_utils.console.print') as mock_print:
        with pytest.raises(typer.Exit) as exc_info:
            failing_func()
        assert exc_info.value.exit_code == 1
        assert mock_print.called
        call_args_list = [str(call[0][0]) for call in mock_print.call_args_list]
        error_printed = any(('❌ Command failed unexpectedly' in arg for arg in call_args_list))
        assert error_printed

def test_core_command_dispose_engine_called():
    """Test that dispose_engine is called in finally block."""

    @core_command(requires_context=False)
    def simple_func():
        return 'done'
    with patch('shared.cli_utils.dispose_engine') as mock_dispose:
        result = simple_func()
        assert result == 'done'
        assert mock_dispose.called

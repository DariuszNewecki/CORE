"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: core_command
- Status: 14 tests passed, some failed
- Passing tests: test_core_command_registers_metadata, test_core_command_with_sync_function_no_context, test_core_command_with_async_function_no_context, test_core_command_requires_context_missing, test_core_command_dangerous_mode_dry_run, test_core_command_dangerous_mode_with_write, test_core_command_with_action_result_failure, test_core_command_with_non_none_result, test_core_command_with_none_result, test_core_command_running_inside_existing_loop, test_core_command_exception_handling, test_core_command_typer_exit_propagates, test_core_command_with_context_object, test_core_command_preserves_function_metadata
- Generated: 2026-01-11 10:40:20
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
import typer

from shared.cli_utils import core_command


def test_core_command_registers_metadata():
    """Test that core_command registers function metadata in COMMAND_REGISTRY."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def test_func():
        return "test"

    from shared.cli_utils import COMMAND_REGISTRY

    assert "test_func" in COMMAND_REGISTRY
    metadata = COMMAND_REGISTRY["test_func"]
    assert metadata.dangerous
    assert not metadata.confirmation
    assert not metadata.requires_context


def test_core_command_with_sync_function_no_context():
    """Test core_command with a sync function that doesn't require context."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def sync_func():
        return "sync_result"

    result = sync_func()
    assert result == "sync_result"


def test_core_command_with_async_function_no_context():
    """Test core_command with an async function that doesn't require context."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    async def async_func():
        await asyncio.sleep(0.001)
        return "async_result"

    result = async_func()
    assert result == "async_result"


def test_core_command_requires_context_missing():
    """Test that core_command raises error when context is required but missing."""

    @core_command(dangerous=False, confirmation=False, requires_context=True)
    def func_with_context(ctx: typer.Context):
        return "should_not_reach"

    with pytest.raises(typer.Exit) as exc_info:
        func_with_context()
    assert exc_info.value.exit_code == 1


def test_core_command_dangerous_mode_dry_run():
    """Test dangerous mode with write=False shows dry run warning."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def dangerous_func(write: bool = False):
        return "executed"

    from shared.cli_utils import console

    with patch.object(console, "print") as mock_print:
        result = dangerous_func(write=False)
        assert result == "executed"
        mock_print.assert_any_call(
            "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
        )


def test_core_command_dangerous_mode_with_write():
    """Test dangerous mode with write=True executes normally."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def dangerous_func(write: bool = False):
        return "executed_with_write"

    result = dangerous_func(write=True)
    assert result == "executed_with_write"


def test_core_command_with_action_result_failure():
    """Test core_command exits with code 1 when ActionResult.ok is False."""
    from shared.cli_utils import ActionResult

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def action_func():
        return ActionResult(ok=False, message="Failed", data=None)

    with pytest.raises(typer.Exit) as exc_info:
        action_func()
    assert exc_info.value.exit_code == 1


def test_core_command_with_non_none_result():
    """Test core_command prints non-None, non-ActionResult results."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def func_with_result():
        return "some_result"

    from shared.cli_utils import console

    with patch.object(console, "print") as mock_print:
        result = func_with_result()
        assert result == "some_result"
        mock_print.assert_called_once_with("some_result")


def test_core_command_with_none_result():
    """Test core_command doesn't print None results."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def func_with_none():
        return None

    from shared.cli_utils import console

    with patch.object(console, "print") as mock_print:
        result = func_with_none()
        assert result is None
        mock_print.assert_not_called()


def test_core_command_running_inside_existing_loop():
    """Test core_command raises RuntimeError when called inside running event loop."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def regular_func():
        return "test"

    async def nested_call():
        return regular_func()

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(nested_call())
    assert "CORE CLI commands cannot run inside an already-running event loop" in str(
        exc_info.value
    )


def test_core_command_exception_handling():
    """Test core_command catches exceptions and exits with code 1."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def failing_func():
        raise ValueError("Test error")

    with pytest.raises(typer.Exit) as exc_info:
        failing_func()
    assert exc_info.value.exit_code == 1


def test_core_command_typer_exit_propagates():
    """Test that typer.Exit exceptions are propagated without wrapping."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def exit_func():
        raise typer.Exit(42)

    with pytest.raises(typer.Exit) as exc_info:
        exit_func()
    assert exc_info.value.exit_code == 42


def test_core_command_with_context_object():
    """Test core_command with context parameter and core_context injection."""
    mock_ctx = Mock(spec=typer.Context)
    mock_core_context = Mock()
    mock_core_context.registry = Mock()
    mock_core_context.qdrant_service = None
    mock_core_context.cognitive_service = None
    mock_ctx.obj = mock_core_context

    @core_command(dangerous=False, confirmation=False, requires_context=True)
    async def func_with_ctx(ctx: typer.Context):
        return (
            f"qdrant: {ctx.obj.qdrant_service}, cognitive: {ctx.obj.cognitive_service}"
        )

    mock_qdrant = Mock()
    mock_cognitive = Mock()

    async def mock_get_qdrant():
        return mock_qdrant

    async def mock_get_cognitive():
        return mock_cognitive

    mock_core_context.registry.get_qdrant_service = mock_get_qdrant
    mock_core_context.registry.get_cognitive_service = mock_get_cognitive
    result = func_with_ctx(mock_ctx)
    assert mock_core_context.qdrant_service == mock_qdrant
    assert mock_core_context.cognitive_service == mock_cognitive


def test_core_command_preserves_function_metadata():
    """Test that core_command preserves the wrapped function's metadata."""

    def original_func(x: int, y: str = "default") -> str:
        """Original docstring."""
        return f"{x}_{y}"

    decorated = core_command(
        dangerous=False, confirmation=False, requires_context=False
    )(original_func)
    assert decorated.__name__ == "original_func"
    assert decorated.__doc__ == "Original docstring."
    assert decorated.__module__ == original_func.__module__
    result = decorated(5, y="test")
    assert result == "5_test"

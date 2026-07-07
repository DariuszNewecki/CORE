"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: core_command
- Generated: 2026-01-11 10:40:20
- 2026-06-07 (#572 Cat B batch 11):
    * All 5 ``from shared.cli_utils import X`` imports updated to canonical
      post-split paths: COMMAND_REGISTRY at ``cli.utils.decorators``,
      console at ``cli.utils.decorators`` (the module's own
      ``console = Console()`` at line 31), ActionResult at
      ``shared.action_types``.
    * test_core_command_with_non_none_result reworked: source emits
      non-None / non-ActionResult results via ``logger.info(res)`` at
      line 155, not ``console.print``. Patch the logger instead.
    * test_core_command_running_inside_existing_loop reframed: the
      RuntimeError guard the autogen vintage expected ("CORE CLI commands
      cannot run inside an already-running event loop") no longer exists
      — source at line 111-114 detects a running loop and falls through
      to ``func(*args, **kwargs)`` directly. Same drift shape as
      tests/shared/test_cli_utils.py:test_async_command from batch 8.
    * test_core_command_with_context_object rewritten to capture the
      injected services *during* function execution: source resets all
      three context attributes (qdrant_service, cognitive_service,
      auditor_context) to None in the teardown block (lines 158-165), so
      asserting on post-call state always sees None. Also added
      ``get_auditor_context`` mock — source consults it eagerly even
      though the autogen vintage only mocked the first two registry
      methods.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import typer

from cli.utils.decorators import COMMAND_REGISTRY, console, core_command
from shared.action_types import ActionResult


def test_core_command_registers_metadata():
    """Test that core_command registers function metadata in COMMAND_REGISTRY."""

    @core_command(dangerous=True, confirmation=False, requires_context=False)
    def test_func():
        return "test"

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

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def action_func():
        return ActionResult(ok=False, message="Failed", data=None)

    with pytest.raises(typer.Exit) as exc_info:
        action_func()
    assert exc_info.value.exit_code == 1


def test_core_command_with_non_none_result():
    """Non-None, non-ActionResult results are surfaced via ``logger.info``,
    not ``console.print``. The autogen vintage expected the result to land
    in the console; source's wrapper at line 155 routes it through the
    module logger instead."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def func_with_result():
        return "some_result"

    with patch("cli.utils.decorators.logger") as mock_logger:
        result = func_with_result()
        assert result == "some_result"
        mock_logger.info.assert_called_once_with("some_result")


def test_core_command_with_none_result():
    """A None result is neither logged nor printed."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def func_with_none():
        return None

    with (
        patch.object(console, "print") as mock_print,
        patch("cli.utils.decorators.logger") as mock_logger,
    ):
        result = func_with_none()
        assert result is None
        mock_print.assert_not_called()
        mock_logger.info.assert_not_called()


def test_core_command_running_inside_existing_loop():
    """Inside a running event loop, ``core_command`` does NOT raise — its
    wrapper detects the loop (line 111) and returns ``func(*args, **kwargs)``
    directly, leaving loop management to the caller. The autogen vintage's
    expected RuntimeError guard ("CORE CLI commands cannot run inside an
    already-running event loop") is no longer enforced.

    Same drift shape as tests/shared/test_cli_utils.py:test_async_command
    (batch 8). If the guard should be restored, that's a separate source-
    side decision."""

    @core_command(dangerous=False, confirmation=False, requires_context=False)
    def regular_func():
        return "test"

    async def nested_call():
        # The decorator returns the raw result of ``regular_func()`` here.
        return regular_func()

    result = asyncio.run(nested_call())
    assert result == "test"


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
    """core_command eagerly resolves ``qdrant_service``, ``cognitive_service``,
    and ``auditor_context`` from ``ctx.obj.registry`` before invoking the
    wrapped function, then resets them on the teardown path.

    Important: source's teardown (lines 158-165) explicitly nulls all three
    attributes after the function returns, so asserting on post-call state
    always sees None. The test captures the injected values *during* the
    wrapped function's execution via an out-of-scope dict — the autogen
    vintage's post-call assertions were never satisfiable against the
    teardown semantics, regardless of the import drift."""
    mock_ctx = Mock(spec=typer.Context)
    mock_core_context = Mock()
    mock_core_context.registry = Mock()
    mock_core_context.qdrant_service = None
    mock_core_context.cognitive_service = None
    mock_core_context.auditor_context = None
    mock_ctx.obj = mock_core_context

    mock_qdrant = Mock(name="mock_qdrant")
    mock_cognitive = Mock(name="mock_cognitive")
    mock_auditor = Mock(name="mock_auditor")

    mock_core_context.registry.get_qdrant_service = AsyncMock(return_value=mock_qdrant)
    mock_core_context.registry.get_cognitive_service = AsyncMock(
        return_value=mock_cognitive
    )
    mock_core_context.registry.get_auditor_context = AsyncMock(
        return_value=mock_auditor
    )

    captured: dict[str, object] = {}

    @core_command(dangerous=False, confirmation=False, requires_context=True)
    async def func_with_ctx(ctx: typer.Context):
        captured["qdrant"] = ctx.obj.qdrant_service
        captured["cognitive"] = ctx.obj.cognitive_service
        captured["auditor"] = ctx.obj.auditor_context

    func_with_ctx(mock_ctx)

    assert captured["qdrant"] is mock_qdrant
    assert captured["cognitive"] is mock_cognitive
    assert captured["auditor"] is mock_auditor
    # Teardown reset:
    assert mock_core_context.qdrant_service is None
    assert mock_core_context.cognitive_service is None
    assert mock_core_context.auditor_context is None


def test_core_command_skips_brain_services_when_not_required():
    """``requires_brain_services=False`` must NOT eagerly resolve
    qdrant/cognitive/auditor. An inherently stateless command (e.g.
    ``intent sync vocabulary``) runs in a CI runner with no DB/Qdrant, where
    warming Qdrant raises (``QDRANT_URL`` unset) and warming the cognitive
    service opens a DB session that hangs when the DB is unreachable. The
    warm-up block must be skipped entirely, leaving the three attrs None."""
    mock_ctx = Mock(spec=typer.Context)
    mock_core_context = Mock()
    mock_core_context.registry = Mock()
    mock_core_context.qdrant_service = None
    mock_core_context.cognitive_service = None
    mock_core_context.auditor_context = None
    mock_ctx.obj = mock_core_context

    # Getters that would blow up if the warm-up path touched them.
    mock_core_context.registry.get_qdrant_service = AsyncMock(
        side_effect=ValueError("QDRANT_URL is not configured")
    )
    mock_core_context.registry.get_cognitive_service = AsyncMock(
        side_effect=AssertionError("cognitive warm-up must be skipped")
    )
    mock_core_context.registry.get_auditor_context = AsyncMock(
        side_effect=AssertionError("auditor warm-up must be skipped")
    )

    captured: dict[str, object] = {}

    @core_command(requires_context=True, requires_brain_services=False)
    async def stateless_func(ctx: typer.Context):
        captured["qdrant"] = ctx.obj.qdrant_service
        captured["cognitive"] = ctx.obj.cognitive_service
        captured["auditor"] = ctx.obj.auditor_context

    # Must not raise despite the raising getters — warm-up is skipped entirely.
    stateless_func(mock_ctx)

    assert captured["qdrant"] is None
    assert captured["cognitive"] is None
    assert captured["auditor"] is None
    mock_core_context.registry.get_qdrant_service.assert_not_called()
    mock_core_context.registry.get_cognitive_service.assert_not_called()
    mock_core_context.registry.get_auditor_context.assert_not_called()


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

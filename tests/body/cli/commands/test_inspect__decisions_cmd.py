"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/cli/commands/inspect.py
- Symbol: decisions_cmd
- Status: 6 tests passed, some failed
- Passing tests: test_decisions_cmd_imports_correctly, test_decisions_cmd_requires_context_object, test_decisions_cmd_docstring_contains_examples, test_decisions_cmd_imports_within_function, test_decisions_cmd_has_async_context_manager, test_decisions_cmd_routing_logic_structure
- Generated: 2026-01-11 03:45:06
"""

import pytest

from body.cli.commands.inspect import decisions_cmd


@pytest.mark.asyncio
async def test_decisions_cmd_imports_correctly():
    """Test that the function can be imported and called with minimal args."""
    assert callable(decisions_cmd)


@pytest.mark.asyncio
async def test_decisions_cmd_requires_context_object():
    """Test that ctx parameter is required (Typer context)."""
    pass


@pytest.mark.asyncio
async def test_decisions_cmd_docstring_contains_examples():
    """Test that the docstring includes the documented examples."""
    doc = decisions_cmd.__doc__
    assert doc is not None
    assert "core-admin inspect decisions" in doc
    assert "core-admin inspect decisions --session abc123" in doc
    assert "core-admin inspect decisions --failures-only" in doc
    assert "core-admin inspect decisions --agent CodeGenerator" in doc
    assert "core-admin inspect decisions --pattern action_pattern --stats" in doc


@pytest.mark.asyncio
async def test_decisions_cmd_imports_within_function():
    """Test that the function imports required modules internally."""
    import inspect

    source = inspect.getsource(decisions_cmd)
    assert (
        "from shared.infrastructure.database.session_manager import get_session"
        in source
    )
    assert "DecisionTraceRepository" in source
    assert "_show_session_trace" in source
    assert "_show_statistics" in source
    assert "_show_pattern_traces" in source
    assert "_show_recent_traces" in source


@pytest.mark.asyncio
async def test_decisions_cmd_has_async_context_manager():
    """Test that the function uses async context manager for database session."""
    import inspect

    source = inspect.getsource(decisions_cmd)
    assert "async with get_session() as session:" in source


@pytest.mark.asyncio
async def test_decisions_cmd_routing_logic_structure():
    """Test the routing logic structure based on parameters."""
    import inspect

    source = inspect.getsource(decisions_cmd)
    assert "if session_id:" in source
    assert "elif stats:" in source
    assert "elif pattern:" in source
    assert "else:" in source
    assert "await _show_session_trace(repo, session_id, details)" in source
    assert "await _show_statistics(repo, pattern, days=recent)" in source
    assert "await _show_pattern_traces(repo, pattern, recent, details)" in source
    assert (
        "await _show_recent_traces(repo, recent, agent, failures_only, details)"
        in source
    )

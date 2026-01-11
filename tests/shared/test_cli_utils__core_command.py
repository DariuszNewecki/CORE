"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: core_command
- Status: 3 tests passed, some failed
- Passing tests: test_dangerous_with_confirmation_cancelled, test_missing_context_when_required, test_running_inside_existing_loop
- Generated: 2026-01-11 00:48:44
"""

import pytest
import asyncio
import typer
from typer.testing import CliRunner
from shared.cli_utils import core_command
from typing import Any
from shared.cli_utils import ActionResult

@pytest.mark.asyncio
async def test_dangerous_with_confirmation_cancelled():
    """Test dangerous command when confirmation is cancelled"""
    import shared.cli_utils
    original_confirm = shared.cli_utils.confirm_action
    shared.cli_utils.confirm_action = lambda *args, **kwargs: False
    try:
        with pytest.raises(typer.Exit) as exc_info:
            dangerous_confirmation(write=True)
        assert exc_info.value.exit_code == 0
    finally:
        shared.cli_utils.confirm_action = original_confirm

@pytest.mark.asyncio
async def test_missing_context_when_required():
    """Test error when context is required but not provided"""
    with pytest.raises(typer.Exit) as exc_info:
        sync_with_context(None, value='test')
    assert exc_info.value.exit_code == 1

@pytest.mark.asyncio
async def test_running_inside_existing_loop():
    """Test error when trying to run inside existing event loop"""

    async def nested_call():
        with pytest.raises(RuntimeError) as exc_info:
            sync_no_context(value='test')
        assert 'already-running event loop' in str(exc_info.value)
    await nested_call()

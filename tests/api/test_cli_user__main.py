"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/api/cli_user.py
- Symbol: main
- Status: 5 tests passed, some failed
- Passing tests: test_main_with_invoked_subcommand, test_main_with_empty_message, test_main_with_none_message, test_main_keyboard_interrupt, test_main_general_exception
- Generated: 2026-01-11 00:45:13
"""

import pytest
import typer
from unittest.mock import patch, MagicMock
import asyncio
import logging
from api.cli_user import main

def test_main_with_invoked_subcommand():
    """Test that main returns early when invoked_subcommand is not None."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = 'some_subcommand'
    result = main(mock_ctx, 'test message')
    assert result is None

def test_main_with_empty_message():
    """Test that main raises typer.Exit(1) when message is empty."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    with pytest.raises(typer.Exit) as exc_info:
        main(mock_ctx, '')
    assert exc_info.value.exit_code == 1

def test_main_with_none_message():
    """Test that main raises typer.Exit(1) when message is None."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    with pytest.raises(typer.Exit) as exc_info:
        main(mock_ctx, None)
    assert exc_info.value.exit_code == 1

def test_main_keyboard_interrupt():
    """Test that main handles KeyboardInterrupt gracefully."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    with patch('api.cli_user.logger') as mock_logger:
        with patch('api.cli_user.asyncio.run') as mock_asyncio_run:
            mock_asyncio_run.side_effect = KeyboardInterrupt()
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, 'test message')
    assert exc_info.value.exit_code == 130
    mock_logger.info.assert_any_call('\n\n⚠️  Interrupted by user')

def test_main_general_exception():
    """Test that main handles general exceptions gracefully."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_exception = Exception('Test error')
    with patch('api.cli_user.logger') as mock_logger:
        with patch('api.cli_user.asyncio.run') as mock_asyncio_run:
            mock_asyncio_run.side_effect = test_exception
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, 'test message')
    assert exc_info.value.exit_code == 1
    mock_logger.error.assert_called_once_with('Failed to process message: %s', test_exception, exc_info=True)
    mock_logger.info.assert_any_call('\n❌ Error: %s', test_exception)

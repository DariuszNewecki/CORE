"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/api/cli_user.py
- Symbol: main
- Status: 7 tests passed, some failed
- Passing tests: test_main_with_invoked_subcommand, test_main_with_empty_message, test_main_with_none_message, test_main_keyboard_interrupt, test_main_general_exception, test_main_logs_user_message, test_main_example_messages
- Generated: 2026-01-11 00:01:52
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
    with patch('api.cli_user.handle_message', side_effect=KeyboardInterrupt):
        with patch('api.cli_user.asyncio.run') as mock_asyncio_run:
            mock_asyncio_run.side_effect = KeyboardInterrupt
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, 'test message')
            assert exc_info.value.exit_code == 130

def test_main_general_exception():
    """Test that main handles general exceptions gracefully."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_exception = Exception('Test error')
    with patch('api.cli_user.handle_message', side_effect=test_exception):
        with patch('api.cli_user.asyncio.run') as mock_asyncio_run:
            mock_asyncio_run.side_effect = test_exception
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, 'test message')
            assert exc_info.value.exit_code == 1

def test_main_logs_user_message(caplog):
    """Test that main logs the user message."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_message = 'what does ContextBuilder do?'
    with patch('api.cli_user.handle_message'):
        with patch('api.cli_user.asyncio.run'):
            with caplog.at_level(logging.INFO):
                result = main(mock_ctx, test_message)
                assert any((f'User message: {test_message}' in record.message for record in caplog.records))
                assert result is None

def test_main_example_messages():
    """Test main with example messages from docstring."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    example_messages = ['analyze the CoreContext class', 'what does ContextBuilder do?', 'my tests are failing', 'refactor this file for clarity']
    for message in example_messages:
        with patch('api.cli_user.handle_message'):
            with patch('api.cli_user.asyncio.run'):
                result = main(mock_ctx, message)
                assert result is None

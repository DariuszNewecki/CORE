"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/api/cli_user.py
- Symbol: main
- Status: 6 tests passed, some failed
- Passing tests: test_main_without_message_shows_usage_and_exits, test_main_with_invoked_subcommand_returns_early, test_main_logs_user_message_and_calls_handler, test_main_handles_keyboard_interrupt, test_main_handles_general_exception, test_main_with_empty_string_message
- Generated: 2026-01-11 10:36:15
"""

from unittest.mock import MagicMock, patch

import pytest
import typer

from api.cli_user import main


def test_main_without_message_shows_usage_and_exits():
    """Test that main shows usage info and exits when no message is provided."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    with patch("api.cli_user.logger") as mock_logger:
        with pytest.raises(typer.Exit) as exc_info:
            main(mock_ctx, message=None)
        assert exc_info.value.exit_code == 1
        mock_logger.info.assert_any_call("Usage: core <message>")
        mock_logger.info.assert_any_call('Example: core "what does ContextBuilder do?"')


def test_main_with_invoked_subcommand_returns_early():
    """Test that main returns early when a subcommand is invoked."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = "some_subcommand"
    result = main(mock_ctx, message="some message")
    assert result is None


def test_main_logs_user_message_and_calls_handler():
    """Test that main logs the user message and calls the async handler."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_message = "analyze the CoreContext class"
    with patch("api.cli_user.logger") as mock_logger:
        with patch("api.cli_user.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = None
            result = main(mock_ctx, message=test_message)
            mock_logger.info.assert_called_with("User message: %s", test_message)
            mock_asyncio_run.assert_called_once()
            assert result is None


def test_main_handles_keyboard_interrupt():
    """Test that main handles KeyboardInterrupt gracefully."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_message = "what does ContextBuilder do?"
    with patch("api.cli_user.logger") as mock_logger:
        with patch("api.cli_user.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.side_effect = KeyboardInterrupt()
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, message=test_message)
            assert exc_info.value.exit_code == 130
            mock_logger.info.assert_called_with("\n\n⚠️  Interrupted by user")


def test_main_handles_general_exception():
    """Test that main handles general exceptions and logs appropriately."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    test_message = "refactor this file for clarity"
    test_exception = Exception("Test error message")
    with patch("api.cli_user.logger") as mock_logger:
        with patch("api.cli_user.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.side_effect = test_exception
            with pytest.raises(typer.Exit) as exc_info:
                main(mock_ctx, message=test_message)
            assert exc_info.value.exit_code == 1
            mock_logger.error.assert_called_with(
                "Failed to process message: %s", test_exception, exc_info=True
            )
            mock_logger.info.assert_called_with("\n❌ Error: %s", test_exception)


def test_main_with_empty_string_message():
    """Test that main treats empty string as no message."""
    mock_ctx = MagicMock(spec=typer.Context)
    mock_ctx.invoked_subcommand = None
    with patch("api.cli_user.logger") as mock_logger:
        with pytest.raises(typer.Exit) as exc_info:
            main(mock_ctx, message="")
        assert exc_info.value.exit_code == 1
        mock_logger.info.assert_any_call("Usage: core <message>")

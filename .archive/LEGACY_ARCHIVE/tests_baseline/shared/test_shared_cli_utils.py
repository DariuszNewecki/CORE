# tests/shared/test_shared_cli_utils.py
"""
Tests for shared CLI utilities.
Refactored to match the Constitutional CLI Framework implementation.
"""

from unittest.mock import AsyncMock, patch

from shared.cli_utils import (
    async_command,
    display_error,
    display_info,
    display_success,
    display_warning,
)


def test_async_command():
    """Test that async_command properly wraps and runs an async function."""
    mock_async_func = AsyncMock(return_value="test_result")
    decorated_func = async_command(mock_async_func)

    result = decorated_func("arg1", kwarg1="value1")

    mock_async_func.assert_called_once_with("arg1", kwarg1="value1")
    assert result == "test_result"


def test_display_success():
    with patch("shared.cli_utils.console") as mock_console:
        test_message = "Operation completed successfully"
        display_success(test_message)
        # Matches src/shared/cli_utils.py implementation:
        # def display_success(msg: str): console.print(f"[bold green]{msg}[/bold green]")
        mock_console.print.assert_called_once_with(
            f"[bold green]{test_message}[/bold green]"
        )


def test_display_error():
    with patch("shared.cli_utils.console") as mock_console:
        test_message = "Test error message"
        display_error(test_message)
        # Matches implementation:
        # def display_error(msg: str): console.print(f"[bold red]{msg}[/bold red]")
        mock_console.print.assert_called_once_with(
            f"[bold red]{test_message}[/bold red]"
        )


def test_display_warning():
    with patch("shared.cli_utils.console") as mock_console:
        test_message = "Test warning message"
        display_warning(test_message)
        # Matches implementation:
        # def display_warning(msg: str): console.print(f"[yellow]{msg}[/yellow]")
        mock_console.print.assert_called_once_with(f"[yellow]{test_message}[/yellow]")


def test_display_info():
    with patch("shared.cli_utils.console") as mock_console:
        test_message = "Test info message"
        display_info(test_message)
        # Matches implementation:
        # def display_info(msg: str): console.print(f"[cyan]{msg}[/cyan]")
        mock_console.print.assert_called_once_with(f"[cyan]{test_message}[/cyan]")

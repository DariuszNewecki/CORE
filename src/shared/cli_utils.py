# src/shared/cli_utils.py
import asyncio
import functools

from rich.console import Console

console = Console()


def async_command(func):
    """Decorator to run async functions in Typer commands."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def confirm_action(message: str, abort_message: str = "Action cancelled") -> bool:
    """Prompt user for confirmation."""
    from rich.prompt import Confirm

    confirmed = Confirm.ask(message, default=False)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    return confirmed


def display_success(message: str) -> None:
    """Display a success message."""
    console.print(f"[green]✓[/green] {message}")


def display_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[bold red]✗ {message}[/bold red]")


def display_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def display_info(message: str) -> None:
    """Display an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")

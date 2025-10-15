# src/shared/cli_utils.py
import asyncio
import functools

from rich.console import Console

console = Console()


# ID: b922c2ce-45df-4107-93e8-2407095cb25f
def async_command(func):
    """Decorator to run async functions in Typer commands."""

    @functools.wraps(func)
    # ID: 7b95eef7-d454-4531-9deb-dc80e1e41d93
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


# ID: 6471fd1b-d2fe-47a3-9dff-e59c2fe09b81
def confirm_action(message: str, abort_message: str = "Action cancelled") -> bool:
    """Prompt user for confirmation."""
    from rich.prompt import Confirm

    confirmed = Confirm.ask(message, default=False)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    return confirmed


# ID: 2727c44e-1884-4a42-9174-ba84d9beb184
def display_success(message: str) -> None:
    """Display a success message."""
    console.print(f"[green]✓[/green] {message}")


# ID: b08bd490-da72-4fff-920b-76b7bd1c2f80
def display_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[bold red]✗ {message}[/bold red]")


# ID: 8a167e1c-dca9-4c30-929c-bde2fa0836fd
def display_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


# ID: ebd53aa4-f448-4cd8-9d55-4d0adb16648f
def display_info(message: str) -> None:
    """Display an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")

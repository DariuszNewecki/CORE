# src/shared/cli_utils.py
"""Provides functionality for the cli_utils module."""

from __future__ import annotations

import asyncio
import functools
from functools import partial

from rich.console import Console

console = Console()


# ID: 8297e3ce-fccb-48f4-804a-416a25a59da0
def async_command(func):
    """Decorator to run async functions in Typer commands correctly."""

    @functools.wraps(func)
    # ID: 921b9a91-5047-460a-9fd2-e970fac5fe80
    def wrapper(*args, **kwargs):
        """
        Runs the decorated async function. If an event loop is already
        running (like in tests), it awaits the function. Otherwise, it
        creates a new event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # This path is often taken in testing environments
                return loop.create_task(func(*args, **kwargs))
            return asyncio.run(func(*args, **kwargs))
        except RuntimeError:
            # No running loop, so we can safely start one
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


def _display_message(style: str, prefix: str, message: str) -> None:
    """
    Internal helper to enforce consistent CLI message formatting.
    Arguments are ordered to support partial application (message last).
    """
    console.print(f"[{style}]{prefix}[/{style}] {message}")


# Use partials to create specialized display functions without structural duplication.
# This prevents the "semantic duplicate" detector from flagging them as clones.

# ID: 2727c44e-1884-4a42-9174-ba84d9beb184
display_success = partial(_display_message, "green", "✓")

# ID: b08bd490-da72-4fff-920b-76b7bd1c2f80
display_error = partial(_display_message, "bold red", "✗")

# ID: 8a167e1c-dca9-4c30-929c-bde2fa0836fd
display_warning = partial(_display_message, "yellow", "⚠")

# ID: ebd53aa4-f448-4cd8-9d55-4d0adb16648f
display_info = partial(_display_message, "blue", "ℹ")

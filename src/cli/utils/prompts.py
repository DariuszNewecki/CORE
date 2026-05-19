# src/cli/utils/prompts.py
"""Refactored logic for src/shared/cli_utils/prompts.py."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm


console = Console(log_time=False, log_path=False)


# ID: 0725138a-8eca-4765-9a9c-31f48b4ed5be
def confirm_action(message: str, *, abort_message: str = "Aborted.") -> bool:
    """Unified confirmation prompt for dangerous operations."""
    console.print()
    confirmed = Confirm.ask(message)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    console.print()
    return confirmed

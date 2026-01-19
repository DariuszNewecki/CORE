# src/shared/cli_utils/prompts.py

"""Refactored logic for src/shared/cli_utils/prompts.py."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm


console = Console(log_time=False, log_path=False)


# ID: e47d7ce6-5936-483f-b834-e46e51079c89
def confirm_action(message: str, *, abort_message: str = "Aborted.") -> bool:
    """Unified confirmation prompt for dangerous operations."""
    console.print()
    confirmed = Confirm.ask(message)
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    console.print()
    return confirmed

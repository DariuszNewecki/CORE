# src/cli/utils/prompts.py
"""Refactored logic for src/shared/cli_utils/prompts.py."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.prompt import Confirm

from cli.utils.exit_codes import EXIT_CONFIG_ERROR


console = Console(log_time=False, log_path=False)


# ID: 0725138a-8eca-4765-9a9c-31f48b4ed5be
def confirm_action(
    message: str,
    *,
    abort_message: str = "Aborted.",
    non_interactive_hint: str | None = None,
) -> bool:
    """Unified confirmation prompt for dangerous operations.

    When no answer can be read (stdin closed: CI, ``ssh host cmd``, an
    agent-driven shell), there is nobody to ask, which is not the same as a
    "no". Instead of letting ``EOFError`` escape as a traceback (#912), it
    prints one line and exits with ``EXIT_CONFIG_ERROR``, naming the caller's
    non-interactive option when there is one. A piped answer
    (``echo y | ...``) still works: that is real input, not a closed stdin.
    """
    console.print()
    try:
        confirmed = Confirm.ask(message)
    except EOFError:
        console.print()  # the prompt line was never terminated by an answer
        console.print(
            "[bold red]Cannot ask for confirmation: no interactive input "
            "(stdin is closed).[/bold red]"
        )
        if non_interactive_hint:
            console.print(non_interactive_hint)
        raise typer.Exit(EXIT_CONFIG_ERROR) from None
    if not confirmed:
        console.print(f"[yellow]{abort_message}[/yellow]")
    console.print()
    return confirmed

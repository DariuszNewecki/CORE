# src/cli/commands/submit.py
"""
Registers the new, high-level 'submit' workflow command.
"""

from __future__ import annotations

from typing import Optional

import typer
from cli.logic.system import integrate_command
from shared.context import CoreContext

submit_app = typer.Typer(
    help="High-level workflow commands for developers.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


# ID: 41b7f91c-34ce-413b-9cc2-bd92252fddf9
def set_context(context: CoreContext):
    """Sets the shared context for commands in this group."""
    global _context
    # Forward the context to the logic module that needs it.
    from cli.logic import system

    system._context = context


submit_app.command(
    "changes",
    help="The primary workflow to integrate staged code changes into the system.",
)(integrate_command)

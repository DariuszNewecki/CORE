# src/cli/commands/submit.py
"""
Registers the new, high-level 'submit' workflow command.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

from typing import Optional

import typer
from cli.logic.cli_utils import set_context as set_logic_context
from cli.logic.context import set_context as canonical_set_context
from cli.logic.system import integrate_command
from shared.context import CoreContext

submit_app = typer.Typer(
    help="High-level workflow commands for developers.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


# ID: 6df2b5e8-9497-4bd0-83e4-d184e5d6adb5
def set_context(context: CoreContext):
    """Sets the shared context for commands in this group."""
    global _context
    _context = canonical_set_context(context)
    # Pass the context down to the logic module that needs it.
    set_logic_context(context, "cli.logic.system")


submit_app.command(
    "changes",
    help="The primary workflow to integrate staged code changes into the system.",
)(integrate_command)

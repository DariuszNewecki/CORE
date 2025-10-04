# src/cli/commands/submit.py
"""Registers the new, high-level 'submit' workflow command."""

from __future__ import annotations

import typer
from cli.logic.cli_utils import set_context as set_shared_context
from cli.logic.system import integrate_command
from shared.context import CoreContext

submit_app = typer.Typer(
    help="High-level workflow commands for developers.",
    no_args_is_help=True,
)

submit_app.command(
    "changes",
    help="The primary workflow to integrate staged code changes into the system.",
)(integrate_command)


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
def register(app: typer.Typer, context: CoreContext):
    """Register the 'submit' command group to the main CLI app."""
    # Pass the context to the logic module.
    set_shared_context(context, "cli.logic.system")
    app.add_typer(submit_app, name="submit")

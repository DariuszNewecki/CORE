# src/cli/commands/inspect.py
"""Registers the new, verb-based 'inspect' command group."""
from __future__ import annotations

import typer

from cli.logic.diagnostics import cli_tree
from cli.logic.guard_cli import register_guard
from cli.logic.status import status
from shared.context import CoreContext

inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)

register_guard(inspect_app)
inspect_app.command("status")(status)
inspect_app.command("command-tree")(cli_tree)


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
def register(app: typer.Typer, context: CoreContext):
    """Register the 'inspect' command group to the main CLI app."""
    app.add_typer(inspect_app, name="inspect")

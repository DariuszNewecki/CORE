# src/cli/commands/inspect.py
"""Registers the new, verb-based 'inspect' command group."""
from __future__ import annotations

import typer

from cli.logic.diagnostics import cli_tree
from cli.logic.duplicates import inspect_duplicates
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

    @inspect_app.command(
        "duplicates", help="Runs only the semantic code duplication check."
    )
    # ID: 9320e199-118e-48b0-a287-3efb007fbced
    def duplicates_command(
        threshold: float = typer.Option(
            0.80,
            "--threshold",
            "-t",
            help="The minimum similarity score to consider a duplicate.",
            min=0.5,
            max=1.0,
        )
    ):
        """Wrapper to pass context and threshold to the inspect_duplicates logic."""
        inspect_duplicates(context=context, threshold=threshold)

    app.add_typer(inspect_app, name="inspect")

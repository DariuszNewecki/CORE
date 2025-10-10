# src/cli/commands/inspect.py
"""Registers the new, verb-based 'inspect' command group."""

from __future__ import annotations

import asyncio

import typer

# --- START: CORRECTED IMPORTS ---
from cli.logic.diagnostics import cli_tree, inspect_vector_drift
from cli.logic.duplicates import inspect_duplicates
from cli.logic.guard_cli import register_guard
from cli.logic.status import status
from cli.logic.symbol_drift import inspect_symbol_drift

# --- END: CORRECTED IMPORTS ---
from shared.context import CoreContext

inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)

register_guard(inspect_app)
inspect_app.command("status")(status)
inspect_app.command("command-tree")(cli_tree)
inspect_app.command(
    "symbol-drift",
    help="Detects drift between symbols on the filesystem and in the database.",
)(inspect_symbol_drift)
# --- START: REGISTER THE NEW COMMAND ---
inspect_app.command(
    "vector-drift",
    help="Verifies perfect synchronization between PostgreSQL and Qdrant.",
)(lambda: asyncio.run(inspect_vector_drift()))
# --- END: REGISTER THE NEW COMMAND ---


# ID: 444e3d86-1b8c-4d61-af7a-2c42f1c97fa1
def register(app: typer.Typer, context: CoreContext):
    """Register the 'inspect' command group to the main CLI app."""

    @inspect_app.command(
        "duplicates", help="Runs only the semantic code duplication check."
    )
    # ID: ad11a02b-077d-4e17-b5bb-00ed77392bbd
    def duplicates_command(
        threshold: float = typer.Option(
            0.80,
            "--threshold",
            "-t",
            help="The minimum similarity score to consider a duplicate.",
            min=0.5,
            max=1.0,
        ),
    ):
        """Wrapper to pass context and threshold to the inspect_duplicates logic."""
        inspect_duplicates(context=context, threshold=threshold)

    app.add_typer(inspect_app, name="inspect")

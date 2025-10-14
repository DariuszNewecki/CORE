# src/cli/commands/inspect.py
"""
Registers the new, verb-based 'inspect' command group.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

import asyncio

import typer

from cli.logic.diagnostics import cli_tree
from cli.logic.duplicates import inspect_duplicates
from cli.logic.guard_cli import register_guard
from cli.logic.knowledge import find_common_knowledge
from cli.logic.status import status
from cli.logic.symbol_drift import inspect_symbol_drift
from cli.logic.vector_drift import inspect_vector_drift
from shared.context import CoreContext

inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)

_context: CoreContext | None = None


# ID: e1f2a3b4-c5d6-7e8f-9a0b-1c2d3e4f5a6b
def set_context(context: CoreContext):
    """Sets the shared context for the logic layer."""
    global _context
    _context = context


register_guard(inspect_app)
inspect_app.command("status")(status)
inspect_app.command("command-tree")(cli_tree)
inspect_app.command(
    "symbol-drift",
    help="Detects drift between symbols on the filesystem and in the database.",
)(inspect_symbol_drift)
inspect_app.command(
    "vector-drift",
    help="Verifies perfect synchronization between PostgreSQL and Qdrant.",
)(lambda: asyncio.run(inspect_vector_drift()))
inspect_app.command(
    "common-knowledge",
    help="Finds structurally identical helper functions that can be consolidated.",
)(find_common_knowledge)


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
    if not _context:
        raise typer.Exit("Context not set for duplicates command.")
    inspect_duplicates(context=_context, threshold=threshold)

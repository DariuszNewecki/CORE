# src/body/cli/commands/inspect.py
"""
Registers the new, verb-based 'inspect' command group.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from features.self_healing.test_target_analyzer import TestTargetAnalyzer
from rich.console import Console
from rich.table import Table
from shared.context import CoreContext

from body.cli.logic.diagnostics import cli_tree
from body.cli.logic.duplicates import inspect_duplicates
from body.cli.logic.guard_cli import register_guard
from body.cli.logic.knowledge import find_common_knowledge
from body.cli.logic.status import status
from body.cli.logic.symbol_drift import inspect_symbol_drift
from body.cli.logic.vector_drift import inspect_vector_drift

console = Console()
inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)

_context: CoreContext | None = None


# ID: 41a9713d-d4d2-4af5-9fa3-8fba203a2702
def set_context(context: CoreContext):
    """Sets the shared context for the logic layer."""
    global _context
    _context = context


@inspect_app.command("status")
# ID: 43192f07-fb4f-4f45-9d8c-a096ee0142f6
def status_command():
    """Display database connection and migration status."""
    asyncio.run(status())


register_guard(inspect_app)
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
    "test-targets", help="Analyzes a file to find good targets for autonomous testing."
)
# ID: 90629e33-d442-4e29-be05-55603ad8750f
def inspect_test_targets(
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to analyze.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
):
    """
    Identifies and classifies functions in a file as SIMPLE or COMPLEX test targets.
    """
    analyzer = TestTargetAnalyzer()
    targets = analyzer.analyze_file(file_path)

    if not targets:
        console.print("[yellow]No suitable public functions found to analyze.[/yellow]")
        return

    table = Table(
        title="Test Target Analysis", header_style="bold magenta", show_header=True
    )
    table.add_column("Function", style="cyan")
    table.add_column("Complexity", style="magenta", justify="right")
    table.add_column("Classification", style="yellow")
    table.add_column("Reason")

    for target in targets:
        style = "green" if target.classification == "SIMPLE" else "red"
        table.add_row(
            target.name,
            str(target.complexity),
            f"[{style}]{target.classification}[/{style}]",
            target.reason,
        )
    console.print(table)


@inspect_app.command(
    "duplicates", help="Runs only the semantic code duplication check."
)
# ID: c5fc156b-dbad-4a69-976a-8dcf67f4bd7d
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

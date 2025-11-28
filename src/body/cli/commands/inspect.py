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

import body.cli.logic.status as status_logic
from body.cli.logic.diagnostics import cli_tree, find_clusters_command_sync
from body.cli.logic.duplicates import inspect_duplicates
from body.cli.logic.guard_cli import register_guard
from body.cli.logic.knowledge import find_common_knowledge
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
def status_command() -> None:
    """
    Display database connection and migration status.

    Uses `body.cli.logic.status._get_status_report` so it can be mocked in tests
    and reused by other callers.
    """

    async def _run() -> None:
        # IMPORTANT: call via the module so tests patching
        # body.cli.logic.status._get_status_report see this call.
        report = await status_logic._get_status_report()

        # Connection line
        if report.is_connected:
            console.print("Database connection: OK")
        else:
            console.print("Database connection: FAILED")

        # Version line
        if report.db_version:
            console.print(f"Database version: {report.db_version}")
        else:
            console.print("Database version: N/A")

        # Migration status
        pending = list(report.pending_migrations)
        if not pending:
            # Tests expect the period at the end.
            console.print("Migrations are up to date.")
        else:
            console.print(f"Found {len(pending)} pending migrations")
            for mig in sorted(pending):
                console.print(f"- {mig}")

    asyncio.run(_run())


register_guard(inspect_app)

inspect_app.command("command-tree")(cli_tree)

inspect_app.command(
    "find-clusters",
    help="Finds and displays all semantic capability clusters.",
)(find_clusters_command_sync)

inspect_app.command(
    "symbol-drift",
    help="Detects drift between symbols on the filesystem and in the database.",
)(inspect_symbol_drift)


@inspect_app.command(
    "vector-drift",
    help="Verifies perfect synchronization between PostgreSQL and Qdrant.",
)
# ID: vector_drift_cmd_v2
# ID: a5233d60-2ba7-44de-b5d4-1d8766915a86
def vector_drift_command(ctx: typer.Context):
    """CLI wrapper for vector drift inspection with context injection."""
    core_context: CoreContext = ctx.obj
    # Pass the context so JIT injection of QdrantService works
    asyncio.run(inspect_vector_drift(core_context))


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

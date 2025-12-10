# src/body/cli/commands/inspect.py
"""
Registers the verb-based 'inspect' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

import body.cli.logic.status as status_logic
from body.cli.logic.diagnostics import cli_tree, find_clusters_command_sync
from body.cli.logic.duplicates import inspect_duplicates_async
from body.cli.logic.knowledge import find_common_knowledge
from body.cli.logic.symbol_drift import inspect_symbol_drift
from body.cli.logic.vector_drift import inspect_vector_drift
from features.self_healing.test_target_analyzer import TestTargetAnalyzer
from mind.enforcement.guard_cli import register_guard
from shared.cli_utils import core_command
from shared.context import CoreContext


console = Console()
inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)


@inspect_app.command("status")
@core_command(dangerous=False, requires_context=False)
# ID: fc253528-91bc-44bb-ae52-0ba3886d95d5
async def status_command(ctx: typer.Context) -> None:
    """
    Display database connection and migration status.
    """
    # Delegate to logic layer (now awaited directly)
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
        console.print("Migrations are up to date.")
    else:
        console.print(f"Found {len(pending)} pending migrations")
        for mig in sorted(pending):
            console.print(f"- {mig}")


# Register guard commands (e.g. 'guard drift')
# Note: These sub-commands internally manage their own execution for now.
register_guard(inspect_app)


@inspect_app.command("command-tree")
@core_command(dangerous=False, requires_context=False)
# ID: db3b96cc-d4a8-4bb1-9002-5a9b81d96d51
def command_tree_cmd(ctx: typer.Context) -> None:
    """Displays a hierarchical tree view of all available CLI commands."""
    cli_tree()


@inspect_app.command("find-clusters")
@core_command(dangerous=False)
# ID: b3272cb8-f754-4a11-b18d-6ca5efecbd3d
def find_clusters_cmd(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
) -> None:
    """
    Finds and displays all semantic capability clusters.
    """
    # Passing ctx explicitly because find_clusters_command_sync extracts ctx.obj
    find_clusters_command_sync(ctx, n_clusters=n_clusters)


@inspect_app.command("symbol-drift")
@core_command(dangerous=False)
# ID: c08c957a-f5b3-480d-8232-8c8cafe060d5
def symbol_drift_cmd(ctx: typer.Context) -> None:
    """
    Detects drift between symbols on the filesystem and in the database.
    """
    # inspect_symbol_drift handles its own sync/async logic internally
    inspect_symbol_drift()


@inspect_app.command("vector-drift")
@core_command(dangerous=False)
# ID: 79b5e56e-3aa5-4ce0-a693-e051e0fe1dad
async def vector_drift_command(ctx: typer.Context) -> None:
    """
    Verifies perfect synchronization between PostgreSQL and Qdrant.
    """
    core_context: CoreContext = ctx.obj
    # Framework ensures Qdrant is initialized via JIT
    await inspect_vector_drift(core_context)


@inspect_app.command("common-knowledge")
@core_command(dangerous=False)
# ID: bf926e9a-3106-4697-8d96-ade3fb3cad22
def common_knowledge_cmd(ctx: typer.Context) -> None:
    """
    Finds structurally identical helper functions that can be consolidated.
    """
    find_common_knowledge()


@inspect_app.command("test-targets")
@core_command(dangerous=False, requires_context=False)
# ID: fc375cbc-c97f-40b5-a4a9-0fa4a4d7d359
def inspect_test_targets(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to analyze.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Identifies and classifies functions in a file as SIMPLE or COMPLEX test targets.
    """
    analyzer = TestTargetAnalyzer()
    targets = analyzer.analyze_file(file_path)

    if not targets:
        console.print("[yellow]No suitable public functions found to analyze.[/yellow]")
        return

    from rich.table import Table

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


@inspect_app.command("duplicates")
@core_command(dangerous=False)
# ID: 5a340604-58ea-46d2-8841-a308abad5dff
async def duplicates_command(
    ctx: typer.Context,
    threshold: float = typer.Option(
        0.80,
        "--threshold",
        "-t",
        help="The minimum similarity score to consider a duplicate.",
        min=0.5,
        max=1.0,
    ),
) -> None:
    """
    Runs only the semantic code duplication check.
    """
    core_context: CoreContext = ctx.obj
    await inspect_duplicates_async(context=core_context, threshold=threshold)

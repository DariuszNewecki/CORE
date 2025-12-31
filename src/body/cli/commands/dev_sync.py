# src/body/cli/commands/dev_sync.py

"""
Dev Sync Command - Atomic Action Architecture

Constitutional workflow that:
1. Fixes code to be compliant
2. Syncs clean state to DB and vectors

Replaces the monolithic dev_sync with composable atomic actions.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from body.workflows.dev_sync_workflow import DevSyncWorkflow
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext


console = Console()

dev_sync_app = typer.Typer(
    help="Development synchronization workflows",
    no_args_is_help=True,
)


@dev_sync_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
async def dev_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write/--dry-run",
        help="Dry-run by default; use --write to apply changes",
    ),
) -> None:
    """
    Run dev sync workflow: Fix code, then sync to DB/vectors.

    This is the ONE command you run after editing code to:
    1. Make code constitutional (format, IDs, headers, docstrings, logging)
    2. Sync clean code to PostgreSQL knowledge graph
    3. Sync vectors to Qdrant

    By default runs in DRY-RUN mode. Use --write to apply changes.
    """
    core_context: CoreContext = ctx.obj

    console.print()
    console.rule("[bold cyan]CORE Dev Sync Workflow[/bold cyan]")
    console.print(f"[bold]Mode:[/bold] {'WRITE' if write else 'DRY RUN'}")
    console.print(f"[bold]Repo:[/bold] {settings.REPO_PATH}")
    console.print()

    with activity_run("dev.sync") as run:
        # Execute workflow
        workflow = DevSyncWorkflow(core_context=core_context, write=write)
        result = await workflow.execute()

        # Print results
        _print_workflow_results(result, write=write)

        # Exit with error if workflow failed
        if not result.ok:
            console.print("\n[red]✗ Workflow completed with failures[/red]")
            raise typer.Exit(1)

        console.print("\n[green]✓ Workflow completed successfully[/green]")


# ID: b2c3d4e5-f678-90ab-cdef-1234567890ab
def _print_workflow_results(result: Any, write: bool) -> None:
    """Print workflow results in a clean table format."""
    console.print("\n[bold]Workflow Results[/bold]")
    console.print()

    for phase in result.phases:
        # Phase header
        phase_status = "✓" if phase.ok else "✗"
        console.print(
            f"[bold]{phase_status} {phase.name}[/bold] ({phase.duration:.2f}s)"
        )

        # Action table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Action", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Details", style="dim")

        for action in phase.actions:
            status = "[green]✓[/green]" if action.ok else "[red]✗[/red]"
            duration = f"{action.duration_sec:.2f}s"

            # Format details
            details = []
            if action.ok:
                data = action.data or {}
                for key, value in data.items():
                    if key not in ["error", "dry_run", "traceback"]:
                        details.append(f"{key}={value}")
            else:
                error = action.data.get("error", "Unknown error")
                details.append(f"[red]{error}[/red]")

            table.add_row(
                action.action_id,
                status,
                duration,
                ", ".join(details) if details else "-",
            )

        console.print(table)
        console.print()

    # Summary
    console.print("[bold]Summary[/bold]")
    console.print(f"  Total Actions: {result.total_actions}")
    console.print(f"  Duration: {result.total_duration:.2f}s")
    console.print(f"  Status: {'✓ Success' if result.ok else '✗ Failed'}")

    if not result.ok:
        console.print(f"  Failed: {len(result.failed_actions)} actions")

    if not write:
        console.print("\n[yellow]DRY RUN - Use --write to apply changes[/yellow]")

# src/cli/commands/dev_sync.py
"""
Dev Sync Command - Atomic Action Architecture

Constitutional workflow that:
1. Fixes code to be compliant
2. Syncs clean state to DB and vectors

Replaces the monolithic dev_sync with composable atomic actions.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from body.workflows.dev_sync_workflow import DevSyncWorkflow
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.context import CoreContext


console = Console()
dev_sync_app = typer.Typer(
    help="Development synchronization workflows", no_args_is_help=True
)


@dev_sync_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: fbe1973c-5d4b-4495-a37c-dd30beed6389
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
    repo_root = core_context.git_service.repo_path
    console.print()
    console.rule("[bold cyan]CORE Dev Sync Workflow[/bold cyan]")
    logger.info("[bold]Mode:[/bold] %s", "WRITE" if write else "DRY RUN")
    logger.info("[bold]Repo:[/bold] %s", repo_root)
    console.print()
    with activity_run("dev.sync") as run:
        workflow = DevSyncWorkflow(core_context=core_context, write=write)
        result = await workflow.execute()
        _print_workflow_results(result, write=write)
        if not result.ok:
            logger.info("\n[red]✗ Workflow completed with failures[/red]")
            raise typer.Exit(1)
        logger.info("\n[green]✓ Workflow completed successfully[/green]")


def _print_workflow_results(result: Any, write: bool) -> None:
    """Print workflow results in a clean table format."""
    logger.info("\n[bold]Workflow Results[/bold]")
    console.print()
    for phase in result.phases:
        phase_status = "✓" if phase.ok else "✗"
        logger.info(
            "[bold]%s %s[/bold] (%ss)", phase_status, phase.name, phase.duration
        )
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Action", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Details", style="dim")
        for action in phase.actions:
            status = "[green]✓[/green]" if action.ok else "[red]✗[/red]"
            duration = f"{action.duration_sec:.2f}s"
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
        logger.info(table)
        logger.info()
    logger.info("[bold]Summary[/bold]")
    logger.info("  Total Actions: %s", result.total_actions)
    logger.info("  Duration: %ss", result.total_duration)
    logger.info("  Status: %s", "✓ Success" if result.ok else "✗ Failed")
    if not result.ok:
        logger.info("  Failed: %s actions", len(result.failed_actions))
    if not write:
        logger.info("\n[yellow]DRY RUN - Use --write to apply changes[/yellow]")

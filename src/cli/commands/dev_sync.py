# src/cli/commands/dev_sync.py
"""
Dev Sync Command — composite fix + knowledge-graph + vectors.

Thin client over POST /v1/sync/dev-sync (ADR-058 D2). The composite
workflow runs server-side; the CLI dispatches, polls the sync_runs
resource, and renders per-phase outcomes from the result payload.
"""

from __future__ import annotations

import logging
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()
dev_sync_app = typer.Typer(
    help="Development synchronization workflows", no_args_is_help=True
)


@dev_sync_app.command("sync")
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: fbe1973c-5d4b-4495-a37c-dd30beed6389
async def dev_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write/--dry-run",
        help="Dry-run by default; use --write to apply changes",
    ),
) -> None:
    """Run dev sync workflow via POST /v1/sync/dev-sync.

    By default runs in DRY-RUN mode. Use --write to apply changes.
    """
    _ = ctx
    console.print()
    console.rule("[bold cyan]CORE Dev Sync Workflow[/bold cyan]")
    console.print(f"[bold]Mode:[/bold] {'WRITE' if write else 'DRY RUN'}")
    console.print()

    client = CoreApiClient()
    initial = await client.sync_dev_sync(write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]❌ dev-sync failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]❌ Workflow failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)

    result = final.get("result") or {}
    _print_workflow_results(result, write=write)
    if not result.get("ok", False):
        console.print("\n[red]✗ Workflow completed with failures[/red]")
        raise typer.Exit(1)
    console.print("\n[green]✓ Workflow completed successfully[/green]")


def _print_workflow_results(result: dict[str, Any], write: bool) -> None:
    """Render the dev-sync per-phase result payload returned by the API."""
    console.print("\n[bold]Workflow Results[/bold]")
    console.print()
    phases = result.get("phases") or []
    for phase in phases:
        phase_ok = phase.get("ok", False)
        phase_name = phase.get("name", "(unnamed)")
        phase_duration = phase.get("duration", phase.get("duration_sec", 0))
        marker = "✓" if phase_ok else "✗"
        console.print(f"[bold]{marker} {phase_name}[/bold] ({phase_duration}s)")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Action", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Details", style="dim")
        for action in phase.get("actions") or []:
            ok = action.get("ok", False)
            status = "[green]✓[/green]" if ok else "[red]✗[/red]"
            duration = f"{action.get('duration_sec', 0):.2f}s"
            data = action.get("data") or {}
            details: list[str] = []
            if ok:
                for key, value in data.items():
                    if key in ("error", "dry_run", "traceback"):
                        continue
                    details.append(f"{key}={value}")
            else:
                err = data.get("error", "Unknown error")
                details.append(f"[red]{err}[/red]")
            table.add_row(
                str(action.get("action_id", "(unknown)")),
                status,
                duration,
                ", ".join(details) if details else "-",
            )
        console.print(table)
        console.print()

    console.print("[bold]Summary[/bold]")
    console.print(f"  Total Actions: {result.get('total_actions', 0)}")
    console.print(f"  Duration: {result.get('total_duration', 0)}s")
    console.print(f"  Status: {'✓ Success' if result.get('ok', False) else '✗ Failed'}")
    failed = result.get("failed_actions") or []
    if not result.get("ok", False) and failed:
        console.print(f"  Failed: {len(failed)} actions")
    if not write:
        console.print("\n[yellow]DRY RUN - Use --write to apply changes[/yellow]")

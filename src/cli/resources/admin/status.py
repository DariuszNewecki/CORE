# src/cli/resources/admin/status.py
"""
Admin Status Command - Infrastructure Health Sensation.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta
from shared.infrastructure.diagnostic_service import DiagnosticService

from .hub import app


console = Console()


@app.command("status")
@command_meta(
    canonical_name="admin.status",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Sensory check of system infrastructure and connectivity.",
)
@core_command(dangerous=False, requires_context=True)
# ID: 142e8bb4-c0cf-4913-890d-0eaa49913ec0
async def admin_status_cmd(ctx: typer.Context) -> None:
    """
    Perform a sensory check of the Body's physical connections.
    Validates Database, Vector store, and Environment coordinates.
    """
    core_context = ctx.obj
    service = DiagnosticService(core_context.git_service.repo_path)
    console.print(
        "\n[bold cyan]📡 Sensation: Probing System Infrastructure...[/bold cyan]\n"
    )
    connectivity = await service.check_connectivity()
    table = Table(
        title="Infrastructure Connectivity",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")
    for name, result in connectivity.items():
        status_icon = "[green]OK[/green]" if result["ok"] else "[red]FAIL[/red]"
        table.add_row(name.capitalize(), status_icon, result["detail"])
    console.print(table)
    fs_errors = service.check_file_system()
    if not fs_errors:
        console.print("\n[green]✅ All mandatory constitutional roots found.[/green]")
    else:
        console.print("\n[bold red]❌ File System Gaps Detected:[/bold red]")
        for err in fs_errors:
            console.print(f"  [yellow]•[/yellow] {err}")
    all_ok = all(r["ok"] for r in connectivity.values()) and (not fs_errors)
    if all_ok:
        console.print("\n[bold green]🛡️  Body Health: OPTIMAL[/bold green]\n")
    else:
        console.print("\n[bold red]⚠️  Body Health: DEGRADED[/bold red]\n")
        raise typer.Exit(code=1)

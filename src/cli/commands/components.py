# src/cli/commands/components.py

"""Component Discovery — thin renderer over /v1/components.

Per ADR-057 D5 (revised 2026-05-18) the V2 component inventory is served
by the Inspect API surface. This file is now an HTTP client: it calls
GET /v1/components and renders the response as a Rich table — no
shared.*, body.*, mind.*, or will.* imports.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()
components_app = typer.Typer(
    help="Discover and inspect V2 architectural components.", no_args_is_help=True
)


@components_app.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: 7df262ec-7a35-4d7b-b43c-bb4bc786c1d7
async def list_components(
    ctx: typer.Context,
    filter_type: str = typer.Option(
        None, "--type", "-t", help="Filter by package (e.g., Analyzers)"
    ),
) -> None:
    """Lists all registered V2 components across the Mind-Body-Will layers."""
    _ = ctx
    console.print("\n[bold cyan]🔍 CORE Component Discovery[/bold cyan]\n")
    client = CoreApiClient()
    payload = await client.inspect_components(filter_type=filter_type)
    rows = payload.get("components") or []

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Phase", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Component ID", style="bold green")
    table.add_column("Description")

    total_found = 0
    for row in rows:
        phase = row.get("phase", "")
        row_type = row.get("type", "")
        component_id = row.get("component_id", "")
        description = row.get("description", "")
        if row.get("ok", True):
            table.add_row(phase, row_type, component_id, description)
            total_found += 1
        else:
            table.add_row("ERROR", row_type, component_id, f"[red]{description}[/red]")
    console.print(table)
    console.print(
        f"\n[bold green]✅ Found {total_found} active components across the system.[/bold green]\n"
    )

# src/body/cli/commands/components.py

"""
Component Discovery Commands.
Provides visibility into the available V2.2+ architectural building blocks.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.component_primitive import discover_components
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

components_app = typer.Typer(
    help="Discover and inspect V2 architectural components.", no_args_is_help=True
)

# Canonical packages where CORE components reside
COMPONENT_PACKAGES = {
    "Interpreters": "will.interpreters",
    "Analyzers": "body.analyzers",
    "Strategists": "will.strategists",
    "Evaluators": "body.evaluators",
    "Deciders": "will.deciders",
}


@components_app.command("list")
@core_command(dangerous=False, requires_context=False)
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
def list_components(
    ctx: typer.Context,
    filter_type: str = typer.Option(
        None, "--type", "-t", help="Filter by package (e.g., Analyzers)"
    ),
) -> None:
    """
    Lists all registered V2 components across the Mind-Body-Will layers.
    """
    console.print("\n[bold cyan]🔍 CORE Component Discovery[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Phase", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Component ID", style="bold green")
    table.add_column("Description")

    total_found = 0

    for label, package in COMPONENT_PACKAGES.items():
        if filter_type and filter_type.lower() not in label.lower():
            continue

        components = discover_components(package)

        for cid, cls in sorted(components.items()):
            # Instantiate briefly to read metadata
            try:
                instance = cls()
                table.add_row(
                    instance.phase.value.upper(), label, cid, instance.description
                )
                total_found += 1
            except Exception as e:
                table.add_row(
                    "ERROR", label, cid, f"[red]Initialization failed: {e}[/red]"
                )

    console.print(table)
    console.print(
        f"\n[bold green]✅ Found {total_found} active components across the system.[/bold green]\n"
    )


from shared.logger import getLogger

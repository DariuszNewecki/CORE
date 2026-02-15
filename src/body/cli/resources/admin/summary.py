# src/body/cli/resources/admin/summary.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567811

"""
Admin Summary Command - Operational Health Visualization.
Provides a high-level overview of recent Body actions and failures.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.cli.logic.governance.limb_status_service import LimbStatusService
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("summary")
@command_meta(
    canonical_name="admin.summary",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Display a summary of recent operational health and failures.",
)
@core_command(dangerous=False, requires_context=True)
# ID: f1a2b3c4-d5e6-7890-abcd-ef1234567812
async def admin_summary_cmd(
    ctx: typer.Context,
    limit: int = typer.Option(
        15, "--limit", "-n", help="Number of recent actions to analyze."
    ),
) -> None:
    """
    Summarizes the most recent actions in the Body's ledger.
    Explicitly highlights 'Pain Signals' (errors) for human review.
    """
    core_context = ctx.obj
    # Constitutional DI: Pass the session factory from the registry
    service = LimbStatusService(session_factory=core_context.registry.session)

    console.print(
        "\n[bold cyan]🧬 Sensation: Aggregating Limb Health Summary...[/bold cyan]\n"
    )

    health = await service.get_recent_limb_health(limit=limit)

    # 1. Overall Status Panel
    status_color = "green" if health["status"] == "OPTIMAL" else "yellow"
    status_text = (
        f"Limb State  : [bold {status_color}]{health['status']}[/bold {status_color}]\n"
        f"Scan Depth  : {health['total_checked']} actions\n"
        f"Pain Signals: {health['failure_count']} detected"
    )
    console.print(Panel(status_text, title="Operational Sensation", expand=False))

    # 2. Pain Signal Details (The "What's Wrong")
    if health["issues"]:
        console.print(
            "\n[bold red]🚨 Detected Pain Signals (Recent Failures):[/bold red]"
        )
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Action / Neuron", style="cyan")
        table.add_column("Error Message", style="yellow")
        table.add_column("Time", style="dim", justify="right")

        for issue in health["issues"]:
            table.add_row(issue["action"], issue["error"], str(issue["time"])[:19])
        console.print(table)
    else:
        console.print(
            "\n[bold green]✅ System Harmony: No recent pain signals detected in the ledger.[/bold green]"
        )

    console.print()

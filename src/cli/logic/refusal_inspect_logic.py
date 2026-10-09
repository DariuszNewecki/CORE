# src/cli/logic/refusal_inspect_logic.py
"""
Logic for inspecting constitutional refusals.

Provides rich terminal output for:
- Recent refusals with filtering
- Refusal statistics and trends
- Constitutional compliance analysis

Used by: `core-admin inspect refusals` command
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.infrastructure.repositories.refusal_repository import RefusalRepository
from shared.infrastructure.intent.operational_config import load_operational_config


console = Console()

_CFG = load_operational_config().misc


# ID: 4b4da583-c2ba-43ad-a249-720128871385
async def show_recent_refusals(
    limit: int = _CFG.refusal_inspect_default_limit,
    refusal_type: str | None = None,
    component: str | None = None,
    details: bool = False,
) -> None:
    """
    Show recent refusals with optional filtering.

    Args:
        limit: Maximum records to show
        refusal_type: Filter by type (boundary, confidence, etc.)
        component: Filter by component
        details: Show full details
    """
    repo = RefusalRepository()
    refusals = await repo.get_recent(
        limit=limit, refusal_type=refusal_type, component_id=component
    )
    if not refusals:
        console.print("[yellow]No refusals found matching criteria[/yellow]")
        return
    table = Table(title=f"Recent Refusals ({len(refusals)})")
    table.add_column("Type", style="cyan")
    table.add_column("Component", style="green")
    table.add_column("Phase", style="blue")
    table.add_column("Confidence", justify="right")
    table.add_column("Time", style="dim")
    for refusal in refusals:
        confidence_str = f"{refusal.confidence:.0%}" if refusal.confidence else "N/A"
        table.add_row(
            refusal.refusal_type,
            refusal.component_id,
            refusal.phase,
            confidence_str,
            refusal.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
    console.print(table)
    if details and refusals:
        console.print("\n[bold]Most Recent Refusal Details:[/bold]")
        _show_refusal_details(refusals[0])


def _show_refusal_details(refusal) -> None:
    """Show detailed information about a single refusal."""
    details = []
    details.append(f"[bold cyan]Type:[/bold cyan] {refusal.refusal_type}")
    details.append(f"[bold cyan]Component:[/bold cyan] {refusal.component_id}")
    details.append(f"[bold cyan]Phase:[/bold cyan] {refusal.phase}")
    details.append("")
    details.append("[bold yellow]Reason:[/bold yellow]")
    details.append(f"  {refusal.reason}")
    details.append("")
    details.append("[bold green]Suggested Action:[/bold green]")
    details.append(f"  {refusal.suggested_action}")
    details.append("")
    if refusal.original_request:
        details.append("[bold]Original Request:[/bold]")
        request = refusal.original_request
        if len(request) > 200:
            request = request[:200] + "..."
        details.append(f"  {request}")
        details.append("")
    if refusal.context_data:
        details.append("[bold]Context:[/bold]")
        for key, value in refusal.context_data.items():
            details.append(f"  {key}: {value}")
        details.append("")
    details.append(f"[dim]Confidence: {refusal.confidence:.2f}[/dim]")
    details.append(f"[dim]Time: {refusal.created_at}[/dim]")
    if refusal.session_id:
        details.append(f"[dim]Session: {refusal.session_id}[/dim]")
    panel = Panel(
        "\n".join(details), title=f"Refusal {str(refusal.id)[:8]}", border_style="cyan"
    )
    console.print(panel)

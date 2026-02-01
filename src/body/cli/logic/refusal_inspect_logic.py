# src/body/cli/logic/refusal_inspect_logic.py
# ID: cli.logic.refusal_inspect

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

from shared.infrastructure.repositories.refusal_repository import RefusalRepository


console = Console()


# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
async def show_recent_refusals(
    limit: int = 20,
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

    # Create summary table
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

    # Show details if requested
    if details and refusals:
        console.print("\n[bold]Most Recent Refusal Details:[/bold]")
        _show_refusal_details(refusals[0])


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
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
        # Truncate long requests
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
        "\n".join(details),
        title=f"Refusal {str(refusal.id)[:8]}",
        border_style="cyan",
    )
    console.print(panel)


# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
async def show_refusal_statistics(days: int = 7) -> None:
    """
    Show refusal statistics and trends.

    Args:
        days: Number of days to analyze
    """
    repo = RefusalRepository()
    stats = await repo.get_statistics(days=days)

    if stats["total_refusals"] == 0:
        console.print(f"[yellow]No refusals recorded in the last {days} days[/yellow]")
        return

    # Summary
    console.print(f"\n[bold]Refusal Statistics (Last {days} Days)[/bold]")
    console.print(f"Total Refusals: {stats['total_refusals']}")
    console.print(f"Average Confidence: {stats['avg_confidence']:.2%}\n")

    # By Type
    if stats["by_type"]:
        type_table = Table(title="Refusals by Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", justify="right")
        type_table.add_column("Percentage", justify="right")

        total = stats["total_refusals"]
        for refusal_type, count in sorted(
            stats["by_type"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total) * 100
            type_table.add_row(
                refusal_type,
                str(count),
                f"{percentage:.1f}%",
            )

        console.print(type_table)

    # By Component
    if stats["by_component"]:
        console.print()
        comp_table = Table(title="Refusals by Component")
        comp_table.add_column("Component", style="green")
        comp_table.add_column("Count", justify="right")
        comp_table.add_column("Percentage", justify="right")

        total = stats["total_refusals"]
        for component, count in sorted(
            stats["by_component"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total) * 100
            comp_table.add_row(
                component,
                str(count),
                f"{percentage:.1f}%",
            )

        console.print(comp_table)

    # By Phase
    if stats["by_phase"]:
        console.print()
        phase_table = Table(title="Refusals by Phase")
        phase_table.add_column("Phase", style="blue")
        phase_table.add_column("Count", justify="right")
        phase_table.add_column("Percentage", justify="right")

        total = stats["total_refusals"]
        for phase, count in sorted(
            stats["by_phase"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total) * 100
            phase_table.add_row(
                phase,
                str(count),
                f"{percentage:.1f}%",
            )

        console.print(phase_table)


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
async def show_refusals_by_type(refusal_type: str, limit: int = 20) -> None:
    """
    Show refusals of a specific type.

    Args:
        refusal_type: Type to filter (boundary, confidence, etc.)
        limit: Maximum records to show
    """
    repo = RefusalRepository()
    refusals = await repo.get_by_type(refusal_type, limit=limit)

    if not refusals:
        console.print(f"[yellow]No refusals found of type: {refusal_type}[/yellow]")
        return

    console.print(
        f"\n[bold]{refusal_type.capitalize()} Refusals ({len(refusals)})[/bold]\n"
    )

    for i, refusal in enumerate(refusals, 1):
        console.print(f"[cyan]{i}. {refusal.component_id}[/cyan]")
        console.print(f"   Phase: {refusal.phase}")
        console.print(f"   Reason: {refusal.reason[:100]}...")
        console.print(f"   Time: {refusal.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print()


# ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b
async def show_refusals_by_session(session_id: str) -> None:
    """
    Show all refusals for a specific decision trace session.

    Args:
        session_id: Decision trace session ID
    """
    repo = RefusalRepository()
    refusals = await repo.get_by_session(session_id)

    if not refusals:
        console.print(f"[yellow]No refusals found for session: {session_id}[/yellow]")
        return

    console.print(
        f"\n[bold]Refusals in Session {session_id} ({len(refusals)})[/bold]\n"
    )

    for refusal in refusals:
        _show_refusal_details(refusal)
        console.print()

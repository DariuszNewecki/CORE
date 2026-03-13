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

from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.infrastructure.repositories.refusal_repository import RefusalRepository


console = Console()


# ID: 4b4da583-c2ba-43ad-a249-720128871385
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
        logger.info("[yellow]No refusals found matching criteria[/yellow]")
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
    logger.info(table)
    if details and refusals:
        logger.info("\n[bold]Most Recent Refusal Details:[/bold]")
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
    logger.info(panel)


# ID: 6ed8fe95-3088-46bb-87ce-343001399035
async def show_refusal_statistics(days: int = 7) -> None:
    """
    Show refusal statistics and trends.

    Args:
        days: Number of days to analyze
    """
    repo = RefusalRepository()
    stats = await repo.get_statistics(days=days)
    if stats["total_refusals"] == 0:
        logger.info("[yellow]No refusals recorded in the last %s days[/yellow]", days)
        return
    logger.info("\n[bold]Refusal Statistics (Last %s Days)[/bold]", days)
    logger.info("Total Refusals: %s", stats["total_refusals"])
    logger.info("Average Confidence: %s\n", stats["avg_confidence"])
    if stats["by_type"]:
        type_table = Table(title="Refusals by Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", justify="right")
        type_table.add_column("Percentage", justify="right")
        total = stats["total_refusals"]
        for refusal_type, count in sorted(
            stats["by_type"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total * 100
            type_table.add_row(refusal_type, str(count), f"{percentage:.1f}%")
        logger.info(type_table)
    if stats["by_component"]:
        logger.info()
        comp_table = Table(title="Refusals by Component")
        comp_table.add_column("Component", style="green")
        comp_table.add_column("Count", justify="right")
        comp_table.add_column("Percentage", justify="right")
        total = stats["total_refusals"]
        for component, count in sorted(
            stats["by_component"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total * 100
            comp_table.add_row(component, str(count), f"{percentage:.1f}%")
        logger.info(comp_table)
    if stats["by_phase"]:
        logger.info()
        phase_table = Table(title="Refusals by Phase")
        phase_table.add_column("Phase", style="blue")
        phase_table.add_column("Count", justify="right")
        phase_table.add_column("Percentage", justify="right")
        total = stats["total_refusals"]
        for phase, count in sorted(
            stats["by_phase"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / total * 100
            phase_table.add_row(phase, str(count), f"{percentage:.1f}%")
        logger.info(phase_table)


# ID: 89e49163-1450-4c3f-85b4-8cdf47b53c37
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
        logger.info("[yellow]No refusals found of type: %s[/yellow]", refusal_type)
        return
    logger.info(
        "\n[bold]%s Refusals (%s)[/bold]\n", refusal_type.capitalize(), len(refusals)
    )
    for i, refusal in enumerate(refusals, 1):
        logger.info("[cyan]%s. %s[/cyan]", i, refusal.component_id)
        logger.info("   Phase: %s", refusal.phase)
        logger.info("   Reason: %s...", refusal.reason[:100])
        logger.info("   Time: %s", refusal.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info()


# ID: c7576fa4-ec2e-46ba-89e4-feeab36ee0dc
async def show_refusals_by_session(session_id: str) -> None:
    """
    Show all refusals for a specific decision trace session.

    Args:
        session_id: Decision trace session ID
    """
    repo = RefusalRepository()
    refusals = await repo.get_by_session(session_id)
    if not refusals:
        logger.info("[yellow]No refusals found for session: %s[/yellow]", session_id)
        return
    logger.info(
        "\n[bold]Refusals in Session %s (%s)[/bold]\n", session_id, len(refusals)
    )
    for refusal in refusals:
        _show_refusal_details(refusal)
        logger.info()

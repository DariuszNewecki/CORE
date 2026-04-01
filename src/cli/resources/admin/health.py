# src/cli/resources/admin/health.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("health")
@command_meta(
    canonical_name="admin.health",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="View the continuous system health log trend from background observers.",
)
@core_command(dangerous=False, requires_context=False)
# ID: f03440ee-7fa3-4496-921d-77255394464d
async def admin_health_cmd(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of recent health snapshots to show."
    ),
) -> None:
    """
    Reads the system_health_log populated by the continuous ObserverWorker.
    Replaces the legacy 'check audit' active scan with a passive, instant ledger read.
    """
    logger.info("\n[bold cyan]🏥 Continuous System Health Trend[/bold cyan]\n")
    query = text(
        "\n        SELECT observed_at, open_findings, stale_entries, silent_workers, orphaned_symbols\n        FROM core.system_health_log\n        ORDER BY observed_at DESC\n        LIMIT :limit\n    "
    )
    async with get_session() as session:
        result = await session.execute(query, {"limit": limit})
        rows = result.fetchall()
    if not rows:
        logger.info("[yellow]No health logs found. Is the daemon running?[/yellow]")
        return
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Observed At", style="dim")
    table.add_column("Open Findings", justify="right")
    table.add_column("Stale Entries", justify="right")
    table.add_column("Silent Workers", justify="right")
    table.add_column("Orphaned Symbols", justify="right")
    for row in rows:
        f_color = "red" if row.open_findings > 0 else "green"
        s_color = "yellow" if row.stale_entries > 0 else "green"
        w_color = "red" if row.silent_workers > 0 else "green"
        o_color = "yellow" if row.orphaned_symbols > 0 else "green"
        table.add_row(
            row.observed_at.strftime("%Y-%m-%d %H:%M:%S"),
            f"[{f_color}]{row.open_findings}[/{f_color}]",
            f"[{s_color}]{row.stale_entries}[/{s_color}]",
            f"[{w_color}]{row.silent_workers}[/{w_color}]",
            f"[{o_color}]{row.orphaned_symbols}[/{o_color}]",
        )
    console.print(table)
    logger.info(
        "\n[dim]Run `core-admin workers blackboard` to investigate specific findings.[/dim]\n"
    )

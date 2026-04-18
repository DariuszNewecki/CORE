# src/cli/resources/proposals/list.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from body.services.service_registry import service_registry
from cli.logic.autonomy.views import RISK_COLORS, STATUS_COLORS, render_list_table
from cli.utils import core_command
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository


console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 0485ff02-01f2-4f9d-b22d-9fde692b8bf7
async def list_proposals(
    status: str = typer.Option(
        None, "--status", "-s", help="Filter by status (pending, approved, etc.)"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results."),
    full_ids: bool = typer.Option(
        False,
        "--full-ids",
        "-f",
        help="Show complete proposal IDs instead of truncating.",
    ),
) -> None:
    """List recent autonomous proposals and their risk assessments."""
    async with service_registry.session() as session:
        repo = ProposalRepository(session)
        if status:
            try:
                status_enum = ProposalStatus(status.lower())
                proposals = await repo.list_by_status(status_enum, limit=limit)
                title = f"Proposals ({status_enum.value})"
            except ValueError:
                logger.info("[red]Invalid status: %s[/red]", status)
                return
        else:
            proposals = []
            for s in ProposalStatus:
                batch = await repo.list_by_status(s, limit=5)
                proposals.extend(batch)
            title = "Recent Proposals"
    if not proposals:
        console.print("[yellow]No proposals found.[/yellow]")
    elif full_ids:
        table = Table(title=title)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Goal", style="white")
        table.add_column("Status", style="bold")
        table.add_column("Actions", justify="center")
        table.add_column("Risk", justify="center")
        table.add_column("Created", style="dim")
        for p in proposals:
            s_color = STATUS_COLORS.get(p.status.value, "white")
            risk_level = p.risk.overall_risk if p.risk else "unknown"
            r_color = RISK_COLORS.get(risk_level, "white")
            table.add_row(
                p.proposal_id,
                p.goal[:50] + ("..." if len(p.goal) > 50 else ""),
                f"[{s_color}]{p.status.value}[/{s_color}]",
                str(len(p.actions)),
                f"[{r_color}]{risk_level}[/{r_color}]",
                p.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)
    else:
        console.print(render_list_table(proposals, title))

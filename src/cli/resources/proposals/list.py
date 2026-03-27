# src/cli/resources/proposals/list.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.services.service_registry import service_registry
from cli.logic.autonomy.views import render_list_table
from shared.cli_utils import core_command
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
        logger.info("[yellow]No proposals found.[/yellow]")
    else:
        logger.info(render_list_table(proposals, title))

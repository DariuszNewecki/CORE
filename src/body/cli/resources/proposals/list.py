# src/body/cli/resources/proposals/list.py
import typer
from rich.console import Console

from body.cli.logic.autonomy.views import render_list_table
from body.services.service_registry import service_registry
from shared.cli_utils import core_command
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository


console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: c1bf8e9c-285a-4a6b-a92c-a85191958273
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
                console.print(f"[red]Invalid status: {status}[/red]")
                return
        else:
            # Get a mix of recent items across all statuses
            proposals = []
            for s in ProposalStatus:
                batch = await repo.list_by_status(s, limit=5)
                proposals.extend(batch)
            title = "Recent Proposals"

    if not proposals:
        console.print("[yellow]No proposals found.[/yellow]")
    else:
        console.print(render_list_table(proposals, title))

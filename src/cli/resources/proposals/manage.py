# src/cli/resources/proposals/manage.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.services.service_registry import service_registry
from cli.logic.autonomy.views import print_detailed_info, print_execution_summary
from shared.cli_utils import core_command
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_repository import ProposalRepository


console = Console()


@core_command(dangerous=False)
# ID: 9bacc55b-be1d-4f71-a27e-6e83ba176e33
async def show_proposal(
    ctx: typer.Context, proposal_id: str = typer.Argument(...)
) -> None:
    """Show detailed breakdown and risk assessment of a proposal."""
    async with service_registry.session() as session:
        proposal = await ProposalRepository(session).get(proposal_id)
    if not proposal:
        logger.info("[red]Proposal %s not found.[/red]", proposal_id)
        raise typer.Exit(1)
    print_detailed_info(proposal)


@core_command(dangerous=True)
# ID: f2e065f7-c253-4c33-ae0d-5374ffdb8e23
async def approve_proposal(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(...),
    by: str = typer.Option("cli_admin", "--by", help="Approver identity."),
) -> None:
    """Authorize a pending proposal for execution."""
    from will.autonomy.proposal_state_manager import ProposalStateManager

    async with service_registry.session() as session:
        await ProposalStateManager(session).approve(proposal_id, approved_by=by)
        await session.commit()
    logger.info("[green]✅ Proposal %s APPROVED by %s.[/green]", proposal_id, by)


@core_command(dangerous=True, confirmation=True)
# ID: f4cdc45a-2f42-4916-b4e3-a305b5357a9d
async def execute_proposal(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(...),
    write: bool = typer.Option(False, "--write", help="Apply changes to the system."),
) -> None:
    """
    Execute an approved proposal.

    Runs the atomic action sequence defined in the proposal.
    """
    if not write:
        logger.info("[yellow]💡 Dry-run: simulating execution steps...[/yellow]\n")
    executor = ProposalExecutor(ctx.obj)
    result = await executor.execute(proposal_id, write=write)
    if result["ok"]:
        logger.info(
            "\n[bold green]✅ Execution Successful: %s[/bold green]", proposal_id
        )
    else:
        logger.info("\n[bold red]❌ Execution Failed: %s[/bold red]", proposal_id)
    print_execution_summary(result)


@core_command(dangerous=True)
# ID: 4ac3cfc1-feae-440c-b02f-4c57a6a1147d
async def reject_proposal(
    ctx: typer.Context,
    proposal_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason", "-r"),
) -> None:
    """Reject a proposal and prevent its execution."""
    from will.autonomy.proposal_state_manager import ProposalStateManager

    async with service_registry.session() as session:
        await ProposalStateManager(session).reject(proposal_id, reason=reason)
    logger.info("[yellow]🚫 Proposal %s REJECTED.[/yellow]", proposal_id)

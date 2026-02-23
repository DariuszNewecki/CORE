# src/body/cli/resources/proposals/manage.py
import typer
from rich.console import Console

from body.services.service_registry import service_registry
from cli.logic.autonomy.views import print_detailed_info, print_execution_summary
from shared.cli_utils import core_command
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_repository import ProposalRepository


console = Console()


@core_command(dangerous=False)
# ID: 414a736e-519d-4917-99af-7dd789c9bfbd
async def show_proposal(proposal_id: str = typer.Argument(...)) -> None:
    """Show detailed breakdown and risk assessment of a proposal."""
    async with service_registry.session() as session:
        proposal = await ProposalRepository(session).get(proposal_id)

    if not proposal:
        console.print(f"[red]Proposal {proposal_id} not found.[/red]")
        raise typer.Exit(1)

    print_detailed_info(proposal)


@core_command(dangerous=True)
# ID: 86cc4cf5-d2a9-44f8-a02f-4a0251982841
async def approve_proposal(
    proposal_id: str = typer.Argument(...),
    by: str = typer.Option("cli_admin", "--by", help="Approver identity."),
) -> None:
    """Authorize a pending proposal for execution."""
    async with service_registry.session() as session:
        repo = ProposalRepository(session)
        await repo.approve(proposal_id, approved_by=by)
        await session.commit()

    console.print(f"[green]✅ Proposal {proposal_id} APPROVED by {by}.[/green]")


@core_command(dangerous=True, confirmation=True)
# ID: 66492b42-bccf-4ef2-8a7c-91d48ce8acd7
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
        console.print("[yellow]💡 Dry-run: simulating execution steps...[/yellow]\n")

    executor = ProposalExecutor(ctx.obj)
    result = await executor.execute(proposal_id, write=write)

    if result["ok"]:
        console.print(
            f"\n[bold green]✅ Execution Successful: {proposal_id}[/bold green]"
        )
    else:
        console.print(f"\n[bold red]❌ Execution Failed: {proposal_id}[/bold red]")

    print_execution_summary(result)


@core_command(dangerous=True)
# ID: 5241e4ec-9d4a-472b-bea5-a6b230a98d47
async def reject_proposal(
    proposal_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason", "-r"),
) -> None:
    """Reject a proposal and prevent its execution."""
    async with service_registry.session() as session:
        repo = ProposalRepository(session)
        await repo.reject(proposal_id, reason=reason)
        await session.commit()
    console.print(f"[yellow]🚫 Proposal {proposal_id} REJECTED.[/yellow]")

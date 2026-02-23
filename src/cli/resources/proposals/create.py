# src/body/cli/resources/proposals/create.py
import typer
from rich.console import Console

from body.services.service_registry import service_registry
from cli.logic.autonomy.actions import parse_action_options
from shared.cli_utils import core_command
from will.autonomy.proposal import Proposal, ProposalScope
from will.autonomy.proposal_repository import ProposalRepository


console = Console()


@core_command(dangerous=True, requires_context=True)
# ID: 50d1f9eb-cb56-4f81-ad07-3e25cd28dd34
async def create_proposal(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="Strategic goal of the proposal."),
    actions: list[str] = typer.Option(
        [], "--action", "-a", help="Format: action_id:param=value"
    ),
    files: list[str] = typer.Option(
        [], "--file", "-f", help="Specific files affected."
    ),
) -> None:
    """
    Create a new autonomous proposal for system modification.

    Validates the plan and performs an initial risk assessment.
    """
    console.print(f"[bold cyan]📝 Crafting Proposal:[/bold cyan] {goal}")

    proposal_actions = parse_action_options(actions)
    if not proposal_actions:
        console.print(
            "[yellow]⚠️ Warning: No actions specified. Proposal created as placeholder.[/yellow]"
        )

    proposal = Proposal(
        goal=goal,
        actions=proposal_actions,
        scope=ProposalScope(files=files),
        created_by="cli_operator",
    )

    # Risk Assessment (Logic lives in domain model)
    risk = proposal.compute_risk()
    console.print(f"Risk Tier: [bold]{risk.overall_risk.upper()}[/bold]")

    async with service_registry.session() as session:
        await ProposalRepository(session).create(proposal)
        await session.commit()

    console.print(
        f"[green]✅ Proposal created: [bold]{proposal.proposal_id}[/bold][/green]"
    )
    console.print(
        f"[dim]Run 'core-admin proposals approve {proposal.proposal_id}' to authorize.[/dim]"
    )

# src/cli/resources/proposals/create.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.services.service_registry import service_registry
from cli.logic.autonomy.actions import parse_action_options
from cli.utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta
from will.autonomy.proposal import Proposal, ProposalScope
from will.autonomy.proposal_repository import ProposalRepository

from . import app


console = Console()


@app.command("create")
@command_meta(
    canonical_name="proposals.create",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Create a new autonomous proposal.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: e3cc0065-b821-49dd-b90e-df86633d01c6
async def create_proposal(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="Strategic goal of the proposal."),
    actions: list[str] = typer.Option(
        [], "--action", "-a", help="Format: action_id:param=value"
    ),
    files: list[str] = typer.Option(
        [], "--file", "-f", help="Specific files affected."
    ),
    write: bool = typer.Option(
        False, "--write", help="Persist the proposal. Dry-run by default."
    ),
) -> None:
    """
    Create a new autonomous proposal for system modification.

    Validates the plan and performs an initial risk assessment.
    """
    logger.info("[bold cyan]📝 Crafting Proposal:[/bold cyan] %s", goal)
    proposal_actions = parse_action_options(actions)
    if not proposal_actions:
        logger.info(
            "[yellow]⚠️ Warning: No actions specified. Proposal created as placeholder.[/yellow]"
        )
    proposal = Proposal(
        goal=goal,
        actions=proposal_actions,
        scope=ProposalScope(files=files),
        created_by="cli_operator",
    )
    risk = proposal.compute_risk()
    logger.info("Risk Tier: [bold]%s[/bold]", risk.overall_risk.upper())
    if not write:
        logger.info(
            "[yellow]⚠️  DRY RUN MODE — No changes made. Use --write to persist.[/yellow]"
        )
        logger.info("[dim]Proposal goal: %s[/dim]", proposal.goal)
        return
    async with service_registry.session() as session:
        await ProposalRepository(session).create(proposal)
        await session.commit()
    logger.info(
        "[green]✅ Proposal created: [bold]%s[/bold][/green]", proposal.proposal_id
    )
    logger.info(
        "[dim]Run 'core-admin proposals approve %s' to authorize.[/dim]",
        proposal.proposal_id,
    )

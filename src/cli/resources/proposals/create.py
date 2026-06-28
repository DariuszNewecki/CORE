# src/cli/resources/proposals/create.py

import httpx
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.logic.autonomy.actions import parse_action_options
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)


console = Console()


@command_meta(
    canonical_name="proposals.create",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.USER_FACING,
    summary="Create a new autonomous proposal for system modification.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False)
# ID: e3cc0065-b821-49dd-b90e-df86633d01c6
async def create_proposal(
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
    """Create a new autonomous proposal for system modification.

    Validates the plan and performs an initial risk assessment.
    """
    console.print(f"[bold cyan]📝 Crafting Proposal:[/bold cyan] {goal}")
    proposal_actions = parse_action_options(actions)
    if not proposal_actions:
        console.print(
            "[yellow]⚠️ Warning: No actions specified. "
            "Proposal created as placeholder.[/yellow]"
        )

    client = CoreApiClient()
    try:
        response = await client.create_proposal(
            goal=goal,
            actions=proposal_actions,
            files=files,
            write=write,
        )
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        console.print(f"[red]Proposal creation failed: {detail}[/red]")
        raise typer.Exit(1) from exc

    proposal = response["proposal"]
    risk_level = proposal["risk"]["overall_risk"] if proposal.get("risk") else "unknown"
    console.print(f"Risk Tier: [bold]{risk_level.upper()}[/bold]")

    if not write:
        console.print(
            "[yellow]⚠️  DRY RUN MODE — No changes made. "
            "Use --write to persist.[/yellow]"
        )
        console.print(f"[dim]Proposal goal: {proposal['goal']}[/dim]")
        return

    console.print(
        f"[green]✅ Proposal created: [bold]{proposal['proposal_id']}[/bold][/green]"
    )
    console.print(
        f"[dim]Run 'core-admin proposals approve {proposal['proposal_id']}' to authorize.[/dim]"
    )

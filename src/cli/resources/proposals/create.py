# src/cli/resources/proposals/create.py

import logging

import httpx
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.logic.autonomy.actions import parse_action_options
from cli.utils import core_command

from . import app


# ADR-054 Phase 1 note: the @command_meta decorator was removed
# alongside the will.* / body.* / shared.* import sweep. command_meta
# lives in shared.models, which is forbidden from src/cli/ by
# architecture.cli.api_only. command_sync_service falls back to
# infer_metadata_from_function for this command's registry row.
# Phase 2 (issue #317) will re-home command_meta to a CLI-permitted
# location and reinstate explicit metadata here.

logger = logging.getLogger(__name__)

console = Console()


@app.command("create")
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
    logger.info("[bold cyan]📝 Crafting Proposal:[/bold cyan] %s", goal)
    proposal_actions = parse_action_options(actions)
    if not proposal_actions:
        logger.info(
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
    logger.info("Risk Tier: [bold]%s[/bold]", risk_level.upper())

    if not write:
        logger.info(
            "[yellow]⚠️  DRY RUN MODE — No changes made. "
            "Use --write to persist.[/yellow]"
        )
        logger.info("[dim]Proposal goal: %s[/dim]", proposal["goal"])
        return

    logger.info(
        "[green]✅ Proposal created: [bold]%s[/bold][/green]", proposal["proposal_id"]
    )
    logger.info(
        "[dim]Run 'core-admin proposals approve %s' to authorize.[/dim]",
        proposal["proposal_id"],
    )

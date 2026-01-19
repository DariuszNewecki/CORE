# src/body/cli/commands/manage/proposals.py

"""Refactored logic for src/body/cli/commands/manage/proposals.py."""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from shared.cli_utils import core_command


console = Console()
# THIS NAME MUST MATCH THE IMPORT IN __init__.py
proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.", no_args_is_help=True
)

# Re-using existing logic functions from proposal_service.py
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)


@proposals_sub_app.command("approve")
@core_command(dangerous=True, confirmation=True)
# ID: e82a93be-6869-4c15-bb77-bd1b321038f6
async def approve_command_wrapper(
    ctx: typer.Context,
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
    write: bool = typer.Option(False, "--write", help="Apply the approval."),
) -> None:
    """Approve and apply a constitutional proposal."""
    if not write:
        console.print(
            "[yellow]Dry run not supported for approvals. Use --write to approve.[/yellow]"
        )
        return

    # Pass the context object (CoreContext) to the logic function
    await proposals_approve(context=ctx.obj, proposal_name=proposal_name)

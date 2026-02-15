# src/body/cli/resources/proposals/integrate.py
# ID: 7c2a1a8b-3e5f-49fc-b83c-d922541d25d0

"""
Proposals Integration Action.
Orchestrates the final integration of staged code changes into the system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console

from shared.cli_utils import core_command

from . import app


if TYPE_CHECKING:
    from shared.context import CoreContext

console = Console()


@app.command("integrate")
@core_command(dangerous=False, requires_context=True)
# ID: 9c4ca3d8-dc36-450e-b79d-848c18c118d8
async def integrate_cmd(
    ctx: typer.Context,
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
) -> None:
    """
    Finalize and integrate staged changes into the repository.

    This command performs a high-fidelity integration sequence:
    1. Policy Checks (Governance)
    2. System Tests (Body)
    3. Constitutional Audit (Mind)
    4. Git Commit (Execution)
    """
    from features.project_lifecycle.integration_service import (
        IntegrationError,
        integrate_changes,
    )

    core_context: CoreContext = ctx.obj

    console.print("[bold cyan]🚀 Initiating integration sequence...[/bold cyan]")

    try:
        # The service handles the multi-phase workflow orchestration
        await integrate_changes(context=core_context, commit_message=commit_message)
        console.print(
            "[bold green]✅ Changes successfully integrated and committed.[/bold green]"
        )
    except IntegrationError as exc:
        # core_command handles standard error formatting, we just need to exit
        raise typer.Exit(exc.exit_code) from exc

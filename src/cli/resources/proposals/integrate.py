# src/cli/resources/proposals/integrate.py
"""
Proposals Integration Action.
Orchestrates the final integration of staged code changes into the system.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from cli.utils import core_command

from . import app


if TYPE_CHECKING:
    from shared.context import CoreContext
console = Console()


@app.command("integrate")
@core_command(dangerous=False, requires_context=True)
# ID: f779e122-cafa-44a9-80cc-b4b1a31cc363
async def integrate_cmd(
    ctx: typer.Context,
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
) -> None:
    """
    Finalize and integrate staged changes into the repository.
    """
    from body.project_lifecycle.integration_service import (
        IntegrationError,
        integrate_changes,
    )

    core_context: CoreContext = ctx.obj
    logger.info("[bold cyan]🚀 Initiating integration sequence...[/bold cyan]")
    try:
        await integrate_changes(context=core_context, commit_message=commit_message)
        logger.info(
            "[bold green]✅ Changes successfully integrated and committed.[/bold green]"
        )
    except IntegrationError as exc:
        raise typer.Exit(exc.exit_code) from exc

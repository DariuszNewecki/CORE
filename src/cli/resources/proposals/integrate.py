# src/cli/resources/proposals/integrate.py
"""
Proposals Integration Action.
Orchestrates the final integration of staged code changes into the system.
"""

from __future__ import annotations

import logging

import httpx
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import app


logger = logging.getLogger(__name__)

console = Console()


@app.command("integrate")
@core_command(dangerous=False, requires_context=False)
# ID: f779e122-cafa-44a9-80cc-b4b1a31cc363
async def integrate_cmd(
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
) -> None:
    """Finalize and integrate staged changes into the repository."""
    logger.info("[bold cyan]🚀 Initiating integration sequence...[/bold cyan]")
    client = CoreApiClient()
    try:
        await client.integrate(commit_message=commit_message)
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", {})
        except ValueError:
            detail = {}
        exit_code = (
            (detail or {}).get("exit_code", 1) if isinstance(detail, dict) else 1
        )
        error = (detail or {}).get("error") if isinstance(detail, dict) else str(detail)
        console.print(f"[red]Integration failed: {error or exc.response.text}[/red]")
        raise typer.Exit(exit_code) from exc

    logger.info(
        "[bold green]✅ Changes successfully integrated and committed.[/bold green]"
    )

# src/cli/resources/lane/claim.py
"""`core-admin lane claim` — mark a delegated finding as being worked."""

from __future__ import annotations

import logging

import httpx
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)

console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 6a166026-f99f-4c6c-9a8e-2d415ee10961
async def claim(
    finding_id: str = typer.Argument(
        ..., help="Delegated finding id (from `lane list`/`lane next`)."
    ),
    agent: str = typer.Option(
        "claude-code", "--agent", "-a", help="Identity of the working agent."
    ),
) -> None:
    """Mark a delegated finding as being worked, so it is tracked, not parked.

    Claiming does not change the finding's status — it stays a live lane item —
    it only records who is working it (ADR-109 §2).
    """
    client = CoreApiClient()
    try:
        await client.lane.claim(finding_id, agent=agent)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            console.print(f"[red]Not a live delegated lane item:[/red] {finding_id}")
            raise typer.Exit(code=1) from exc
        raise

    console.print(
        f"[green]Claimed.[/green] Finding [cyan]{finding_id}[/cyan] is now marked "
        f"in-progress by [yellow]{agent}[/yellow]."
    )

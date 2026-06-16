# src/cli/resources/lane/list.py
"""`core-admin lane list` — show the Assisted Remediation Lane work queue."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)

console = Console()

_DEFAULT_LIMIT = 20


@core_command(dangerous=False, requires_context=False)
# ID: 0f0c8d2e-5b4a-4c1e-9a7f-2d3b6e8c1a44
async def list_delegated(
    limit: int = typer.Option(
        _DEFAULT_LIMIT, "--limit", "-n", help="Max delegated findings to show."
    ),
    full_ids: bool = typer.Option(
        False, "--full-ids", "-f", help="Show full finding IDs instead of truncating."
    ),
) -> None:
    """List delegated findings awaiting assisted remediation (indeterminate + human)."""
    client = CoreApiClient()
    response = await client.lane.list_delegated(limit=limit)
    findings = response["findings"]

    if not findings:
        console.print("[green]Lane is empty — no delegated findings.[/green]")
        return

    table = Table(title=f"Assisted Lane — delegated findings ({response['count']})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Subject", style="white")
    table.add_column("Created", style="dim")
    for f in findings:
        fid = f["id"] if full_ids else f["id"][:8]
        created = (f.get("created_at") or "")[:19].replace("T", " ")
        table.add_row(fid, f.get("subject", ""), created)
    console.print(table)

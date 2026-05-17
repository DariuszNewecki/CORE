# src/cli/resources/proposals/list.py
import logging
from datetime import datetime

import httpx
import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.logic.autonomy.views import RISK_COLORS, STATUS_COLORS, render_list_table
from cli.utils import core_command


logger = logging.getLogger(__name__)

console = Console()

_DEFAULT_LIMIT = 20


@core_command(dangerous=False, requires_context=False)
# ID: 0485ff02-01f2-4f9d-b22d-9fde692b8bf7
async def list_proposals(
    status: str = typer.Option(
        None, "--status", "-s", help="Filter by status (pending, approved, etc.)"
    ),
    limit: int = typer.Option(_DEFAULT_LIMIT, "--limit", "-n", help="Max results."),
    full_ids: bool = typer.Option(
        False,
        "--full-ids",
        "-f",
        help="Show complete proposal IDs instead of truncating.",
    ),
) -> None:
    """List recent autonomous proposals and their risk assessments."""
    client = CoreApiClient()
    try:
        response = await client.list_proposals(status=status or None, limit=limit)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            console.print(f"[red]Invalid status: {status}[/red]")
            return
        raise

    proposals = response["proposals"]
    title = f"Proposals ({status})" if status else "Recent Proposals"

    if not proposals:
        console.print("[yellow]No proposals found.[/yellow]")
    elif full_ids:
        table = Table(title=title)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Goal", style="white")
        table.add_column("Status", style="bold")
        table.add_column("Actions", justify="center")
        table.add_column("Risk", justify="center")
        table.add_column("Created", style="dim")
        for p in proposals:
            s = p["status"]
            s_color = STATUS_COLORS.get(s, "white")
            risk_level = p["risk"]["overall_risk"] if p.get("risk") else "unknown"
            r_color = RISK_COLORS.get(risk_level, "white")
            created = datetime.fromisoformat(p["created_at"]).strftime("%Y-%m-%d %H:%M")
            goal = p.get("goal") or ""
            table.add_row(
                p["proposal_id"],
                goal[:50] + ("..." if len(goal) > 50 else ""),
                f"[{s_color}]{s}[/{s_color}]",
                str(len(p.get("actions", []))),
                f"[{r_color}]{risk_level}[/{r_color}]",
                created,
            )
        console.print(table)
    else:
        console.print(render_list_table(proposals, title))

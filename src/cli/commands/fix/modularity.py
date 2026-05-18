# src/cli/commands/fix/modularity.py
"""
Automated Modularity Healing — thin client over POST /v1/fix/modularity.

The endpoint is async (202 + run_id); CLI polls via CoreApiClient._poll_run
and renders the per-file remediation summary that
ModularityRemediationService writes into fix_runs.result.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command("modularity", help="Autonomously modularize architectural offenders.")
@core_command(dangerous=True, confirmation=True)
# ID: ea078c28-eb5f-46ec-b39c-e55cf33714ed
async def fix_modularity_cmd(
    ctx: typer.Context,
    min_score: float = typer.Option(
        None,
        "--score",
        help="Minimum score to trigger healing (defaults to Constitution)",
    ),
    limit: int = typer.Option(
        1, "--limit", "-n", help="Max files to heal in one batch"
    ),
    write: bool = typer.Option(False, "--write", help="Apply changes autonomously"),
) -> None:
    """
    Finds high-complexity files and uses the A3 loop to modularize them.
    """
    params: dict[str, object] = {"limit": limit}
    if min_score is not None:
        params["min_score"] = min_score

    console.print("[bold cyan]CORE is defragmenting architecture...[/bold cyan]")
    client = CoreApiClient()
    initial = await client.fix_modularity(write=write, params=params)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.modularity failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]fix.modularity failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(1)

    result_payload = final.get("result") or {}
    files = result_payload.get("files", [])
    if not files:
        console.print("[green]✅ No files exceed the modularity threshold.[/green]")
        return

    table = Table(title="Modularity Healing Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Initial", justify="right")
    table.add_column("Final", justify="right")
    table.add_column("Delta", style="green", justify="right")
    for res in files:
        status = "✅" if res.get("success") else "❌"
        start_score = res.get("start_score", 0.0)
        final_score = res.get("final_score", 0.0)
        delta = res.get("improvement", 0.0)
        table.add_row(
            res.get("file", ""),
            status,
            f"{start_score:.1f}",
            f"{final_score:.1f}",
            f"-{delta:.1f}" if delta > 0 else "0.0",
        )
    console.print(table)

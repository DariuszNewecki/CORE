# src/cli/commands/fix/body_ui.py
"""
CLI command: `core-admin fix body-ui`

Thin client over POST /v1/quality/body-ui (read) + POST /v1/fix/run/fix.body_ui
(write). Dry-run returns the violation list inline; --write dispatches the
LLM fixer asynchronously and polls.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command("body-ui", help="Fix Body-layer UI contract violations.")
@core_command(dangerous=True, confirmation=True)
# ID: e080af6d-2e0e-4b5d-967b-61c5b7223aaa
async def fix_body_ui_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write/--dry-run",
        help="Dry-run by default; use --write to apply changes.",
    ),
    count: int = typer.Option(
        None,
        "--count",
        "-n",
        help="Limit the number of files to process (for safety/testing).",
    ),
) -> None:
    """
    Fix Body-layer UI/env violations (Rich, print/input, os.environ) using the LLM.

    Dry-run path uses POST /v1/quality/body-ui (sync check) and reports the
    violation count. --write path dispatches POST /v1/fix/run/fix.body_ui
    (async LLM fixer), polls, and reports the summary.
    """
    _ = ctx
    console.print("\n[bold cyan]🔧 Body UI Contracts Fixer[/bold cyan]\n")
    client = CoreApiClient()

    if not write:
        console.print(
            "[yellow]Running in DRY-RUN mode. Use --write to apply changes.[/yellow]\n"
        )
        check = await client.quality_body_ui()
        if check.get("status") == "ok":
            console.print("[green]✓ Body contracts compliant.[/green]")
            return
        violations = check.get("violations", [])
        unique_files = len({v.get("file") for v in violations if v.get("file")})
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Files with violations : {unique_files}")
        console.print(f"  Total violations      : {len(violations)}")
        console.print("  Mode                  : DRY-RUN")
        console.print("\n[yellow]Use --write to apply these changes.[/yellow]")
        return

    if count:
        console.print(f"[dim]Limiting processing to first {count} file(s).[/dim]\n")
    params: dict[str, object] = {}
    if count is not None:
        params["limit"] = count
    initial = await client.run_fix("fix.body_ui", write=True, params=params)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.body_ui failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]fix.body_ui failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)

    result_data = (final.get("result") or {}).get("data", {})
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Files found     : {result_data.get('files_found', 0)}")
    console.print(f"  Files processed : {result_data.get('files_processed', 0)}")
    console.print(f"  Files modified  : {result_data.get('files_modified', 0)}")
    console.print("  Mode            : WRITE")
    console.print("\n[green]✓ Body UI contracts successfully applied.[/green]")

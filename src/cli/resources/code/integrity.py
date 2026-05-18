# src/cli/resources/code/integrity.py
"""
Integrity CLI Commands - Phase 2 Hardening.
Allows the operator to baseline and verify the codebase state.

Thin clients over POST /v1/integrity/{baseline,verify}. All execution
moves server-side; this module only dispatches and renders.
"""

from __future__ import annotations

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()


@app.command("baseline")
@core_command(dangerous=False)
# ID: d76fd565-17ef-4f35-9138-9530efc28324
async def code_baseline_cmd(
    ctx: typer.Context,
    label: str = typer.Option(
        "default", "--label", "-l", help="Label for this baseline."
    ),
) -> None:
    """
    Create a secure checksum baseline of the current 'src/' directory.
    Run this before starting autonomous tasks.
    """
    _ = ctx
    client = CoreApiClient()
    console.print(f"[bold cyan]Creating integrity baseline: {label}...[/bold cyan]")
    result = await client.baseline(label=label)
    path = result.get("path")
    files_hashed = result.get("files_hashed", 0)
    console.print(
        f"[bold green]Baseline stored at: {path} ({files_hashed} files)[/bold green]"
    )


@app.command("verify")
@core_command(dangerous=False)
# ID: 56975e9b-9040-4c0e-bdc4-76b7c68c5abd
async def code_verify_cmd(
    ctx: typer.Context,
    label: str = typer.Option(
        "default", "--label", "-l", help="Baseline label to verify against."
    ),
) -> None:
    """
    Verify the current codebase against a previously created baseline.
    Detects any unauthorized MODIFICATIONS, DELETIONS, or NEW files.
    """
    _ = ctx
    client = CoreApiClient()
    console.print(
        f"[bold cyan]Verifying code integrity against baseline: {label}...[/bold cyan]"
    )
    result = await client.verify(label=label)
    if result.get("ok"):
        console.print(
            "[bold green]Integrity verified: no unauthorized changes detected.[/bold green]"
        )
    else:
        console.print("[bold red]Integrity violation found.[/bold red]")
        for error in result.get("errors", []):
            console.print(f"  [yellow]-[/yellow] {error}")
        raise typer.Exit(code=1)

# src/body/cli/resources/code/integrity.py
# ID: b17e7b0a-aeb2-4c32-a39f-b9d293fa5236

"""
Integrity CLI Commands - Phase 2 Hardening.
Allows the operator to baseline and verify the codebase state.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.infrastructure.storage.integrity_service import IntegrityService

from .hub import app


console = Console()


@app.command("baseline")
@core_command(dangerous=False, requires_context=True)
# ID: 65b8d971-364e-45c3-af9a-52004dd0ceb4
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
    core_context = ctx.obj
    service = IntegrityService(core_context.git_service.repo_path)

    console.print(f"[bold cyan]🔐 Creating integrity baseline: {label}...[/bold cyan]")
    path = service.create_baseline(label)

    console.print(f"[bold green]✅ Success![/bold green] Baseline stored at: {path}")


@app.command("verify")
@core_command(dangerous=False, requires_context=True)
# ID: 67a4cf17-e8b8-4517-9ced-a3360d752f87
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
    core_context = ctx.obj
    service = IntegrityService(core_context.git_service.repo_path)

    console.print(
        f"[bold cyan]🔍 Verifying code integrity against baseline: {label}...[/bold cyan]"
    )
    result = service.verify_integrity(label)

    if result.ok:
        console.print(
            "[bold green]✅ Integrity Verified: No unauthorized changes detected.[/bold green]"
        )
    else:
        console.print("[bold red]❌ Integrity Violation Found![/bold red]")
        for error in result.errors:
            console.print(f"  [yellow]•[/yellow] {error}")

        # Exit with error code to support CI/CD pipelines
        raise typer.Exit(code=1)

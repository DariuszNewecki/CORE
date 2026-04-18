# src/cli/resources/code/integrity.py
"""
Integrity CLI Commands - Phase 2 Hardening.
Allows the operator to baseline and verify the codebase state.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.infrastructure.storage.integrity_service import IntegrityService

from .hub import app


console = Console()


@app.command("baseline")
@core_command(dangerous=False, requires_context=True)
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
    core_context = ctx.obj
    service = IntegrityService(core_context.git_service.repo_path)
    logger.info("[bold cyan]🔐 Creating integrity baseline: %s...[/bold cyan]", label)
    path = service.create_baseline(label)
    logger.info("[bold green]✅ Success![/bold green] Baseline stored at: %s", path)


@app.command("verify")
@core_command(dangerous=False, requires_context=True)
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
    core_context = ctx.obj
    service = IntegrityService(core_context.git_service.repo_path)
    logger.info(
        "[bold cyan]🔍 Verifying code integrity against baseline: %s...[/bold cyan]",
        label,
    )
    result = service.verify_integrity(label)
    if result.ok:
        logger.info(
            "[bold green]✅ Integrity Verified: No unauthorized changes detected.[/bold green]"
        )
    else:
        logger.info("[bold red]❌ Integrity Violation Found![/bold red]")
        for error in result.errors:
            logger.info("  [yellow]•[/yellow] %s", error)
        raise typer.Exit(code=1)

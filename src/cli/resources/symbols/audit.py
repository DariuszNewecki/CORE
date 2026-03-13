# src/cli/resources/symbols/audit.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic.diagnostics import get_unassigned_symbols_logic
from cli.logic.symbol_drift import inspect_symbol_drift
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: 2c32679a-ad9d-48e3-8cb0-b4cec7adea29
async def audit_symbols(ctx: typer.Context) -> None:
    """
    Audit symbol integrity and detect registry drift.

    Checks for:
    1. Symbols missing IDs (Anchors).
    2. Symbols in DB that no longer exist on disk (Ghosts).
    3. Symbols on disk not yet in DB (Drift).
    """
    core_context = ctx.obj
    logger.info(
        "[bold cyan]🔍 1. Checking for Symbol Drift (Disk vs DB)...[/bold cyan]"
    )
    await inspect_symbol_drift()
    logger.info("\n[bold cyan]🔍 2. Checking for Unassigned IDs...[/bold cyan]")
    unassigned = await get_unassigned_symbols_logic(core_context)
    if not unassigned:
        logger.info("[green]✅ All public symbols have assigned IDs.[/green]")
    else:
        logger.info(
            "[yellow]⚠️  Found %s symbols with no ID tag.[/yellow]", len(unassigned)
        )
        for item in unassigned[:10]:
            logger.info("   - %s (%s)", item.get("name"), item.get("file_path"))
        if len(unassigned) > 10:
            logger.info("   ... and %s more.", len(unassigned) - 10)
        logger.info(
            "\n[dim]Tip: Run 'core-admin symbols fix-ids --write' to fix this.[/dim]"
        )

# src/cli/commands/fix/body_ui.py
"""
CLI command: `core-admin fix body-ui`

Runs the Body UI fixer that:
- Detects Body-layer UI/env violations (Rich, print/input, os.environ)
- Uses an LLM to rewrite affected modules to be HEADLESS
- Respects write/dry-run semantics

This module lives in the CLI/Workflow layer, so it is allowed to:
- Use Rich for terminal output
- Own progress messages and summaries
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic.body_contracts_fixer import fix_body_ui_violations
from cli.utils import core_command
from shared.activity_logging import activity_run, log_activity
from shared.context import CoreContext

from . import fix_app


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

    In DRY-RUN mode:
      - No files are written.
      - You still see how many files *would* be modified.

    With --write:
      - Violating files are overwritten with the LLM's corrected versions.
    """
    core_context: CoreContext = ctx.obj
    dry_run = not write
    logger.info("\n[bold cyan]🔧 Body UI Contracts Fixer[/bold cyan]\n")
    if dry_run:
        logger.info(
            "[yellow]Running in DRY-RUN mode. Use --write to apply changes.[/yellow]\n"
        )
    if count:
        logger.info("[dim]Limiting processing to first %s file(s).[/dim]\n", count)
    with activity_run("fix.body-ui") as run:
        result = await fix_body_ui_violations(
            core_context=core_context, write=write, limit=count
        )
        log_activity(
            run,
            event="fix_summary",
            status="ok" if result.ok else "warning",
            details={
                "files_found": result.data.get("files_found", 0),
                "files_processed": result.data.get("files_processed", 0),
                "files_modified": result.data.get("files_modified", 0),
                "dry_run": result.data.get("dry_run", True),
            },
        )
    files_processed = result.data.get("files_processed", 0)
    files_modified = result.data.get("files_modified", 0)
    files_found = result.data.get("files_found", 0)
    logger.info("[bold]Summary:[/bold]")
    logger.info("  Files found     : %s", files_found)
    logger.info("  Files processed : %s", files_processed)
    logger.info("  Files modified  : %s", files_modified)
    logger.info("  Mode            : %s", "DRY-RUN" if dry_run else "WRITE")
    if not result.ok:
        logger.info(
            "\n[red]✖ Some issues occurred during Body UI fixing. Check logs or JSON output for details.[/red]"
        )
        raise typer.Exit(1)
    if dry_run:
        logger.info("\n[yellow]Use --write to apply these changes.[/yellow]")
    else:
        logger.info("\n[green]✓ Body UI contracts successfully applied.[/green]")

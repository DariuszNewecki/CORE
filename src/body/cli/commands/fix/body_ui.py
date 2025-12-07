# src/body/cli/commands/fix/body_ui.py
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

import typer
from rich.console import Console

from body.cli.logic.body_contracts_fixer import fix_body_ui_violations
from shared.activity_logging import activity_run, log_activity
from shared.cli_utils import core_command
from shared.context import CoreContext

# Import the parent app to register this command
from . import fix_app


console = Console()


@fix_app.command("body-ui", help="Fix Body-layer UI contract violations.")
@core_command(dangerous=True, confirmation=True)
# ID: 1eadbb5a-298c-4dc4-a03b-05e7af670c6b
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

    console.print("\n[bold cyan]🔧 Body UI Contracts Fixer[/bold cyan]\n")

    if dry_run:
        console.print(
            "[yellow]Running in DRY-RUN mode. Use --write to apply changes.[/yellow]\n"
        )

    if count:
        console.print(f"[dim]Limiting processing to first {count} file(s).[/dim]\n")

    with activity_run("fix.body-ui") as run:
        # Call the service logic with correct arguments
        result = await fix_body_ui_violations(
            core_context=core_context,
            write=write,
            limit=count,
        )

        # Log result to activity stream
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

    console.print("[bold]Summary:[/bold]")
    console.print(f"  Files found     : {files_found}")
    console.print(f"  Files processed : {files_processed}")
    console.print(f"  Files modified  : {files_modified}")
    console.print(f"  Mode            : {'DRY-RUN' if dry_run else 'WRITE'}")

    if not result.ok:
        console.print(
            "\n[red]✖ Some issues occurred during Body UI fixing. "
            "Check logs or JSON output for details.[/red]"
        )
        raise typer.Exit(1)

    if dry_run:
        console.print("\n[yellow]Use --write to apply these changes.[/yellow]")
    else:
        console.print("\n[green]✓ Body UI contracts successfully applied.[/green]")

# src/body/cli/resources/code/logging.py
# ID: 63c77e0f-e0cf-49f5-b9ac-925edc4854f8

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("logging")
@core_command(dangerous=True, requires_context=True)
# ID: c149a7d3-60b5-4810-abd3-ab87aaf4f9af
async def fix_logging_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Convert print() to logger calls."
    ),
) -> None:
    """
    Standardize logging across the codebase.

    Replaces print() statements and malformed f-strings in loggers with
    constitutional standard logging (LOG-001/LOG-003).
    """
    core_context: CoreContext = ctx.obj

    mode = "Applying" if write else "Analyzing"
    console.print(f"[bold cyan]🪵  {mode} Logging Standards...[/bold cyan]")

    # Routes to the fix.logging atomic action
    await core_context.action_executor.execute("fix.logging", write=write)

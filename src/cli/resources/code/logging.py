# src/cli/resources/code/logging.py
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


console = Console()


@app.command("logging")
@command_meta(
    canonical_name="code.logging",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Standardize logging across the codebase.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False)
# ID: 5076493c-79a8-4f92-8c15-ddfd695d4275
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
    mode = "Applying" if write else "Analyzing"
    console.print(f"[bold cyan]🪵  {mode} Logging Standards...[/bold cyan]")
    client = CoreApiClient()
    initial = await client.run_fix("fix.logging", write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.logging failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]fix.logging failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    console.print("[green]✓ fix.logging completed.[/green]")

# src/cli/resources/code/format.py
import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


async def _run_and_poll(fix_id: str, *, write: bool) -> None:
    client = CoreApiClient()
    initial = await client.run_fix(fix_id, write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]{fix_id} failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]{fix_id} failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)


@app.command("format")
@core_command(dangerous=True, requires_context=False)
# ID: 3dfcec28-34fd-44d4-9aec-bcbf29eb6d76
async def format_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply formatting changes to disk."
    ),
) -> None:
    """
    Format code using Black and Ruff.

    Defaults to dry-run mode. Use --write to apply changes.
    """
    mode = "Applying" if write else "Checking"
    console.print(f"[bold cyan]✨ {mode} code formatting (Black + Ruff)...[/bold cyan]")
    await _run_and_poll("fix.format", write=write)
    if not write:
        console.print("[yellow]💡 Run with --write to apply these changes.[/yellow]")


@app.command("format-imports")
@core_command(dangerous=True, requires_context=False)
# ID: 582d69b9-6f50-411a-a950-37e66ce2e07b
async def format_imports_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply import sorting to disk."),
) -> None:
    """
    Sort and group Python imports according to PEP 8 / Constitutional standards.
    Uses Ruff's import sorter (I) rules.
    """
    await _run_and_poll("fix.imports", write=write)

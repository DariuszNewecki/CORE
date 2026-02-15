# src/body/cli/resources/symbols/sync.py
import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("sync")
@core_command(dangerous=True, requires_context=True)
# ID: 1dfb133f-582d-4817-9450-c0c79e184c50
async def sync_symbols(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply synchronization to the database."
    ),
) -> None:
    """
    Synchronize filesystem symbols with the PostgreSQL Knowledge Graph.

    Scans 'src/' and updates the 'core.symbols' table.
    """
    core_context: CoreContext = ctx.obj

    mode = "WRITE" if write else "DRY-RUN"
    console.print(
        f"[bold cyan]\U0001f504 Synchronizing Symbols to DB ({mode})...[/bold cyan]"
    )

    # Execute via canonical ActionExecutor
    await core_context.action_executor.execute("sync.db", write=write)

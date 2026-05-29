# src/cli/resources/symbols/sync.py
import typer
from rich.console import Console

from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("sync")
@command_meta(
    canonical_name="database.sync-symbols",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize database with codebase symbols.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 7de43597-32ac-4e0f-9e55-af90f4c716f6
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
    console.print(f"[bold cyan]🔄 Synchronizing Symbols to DB ({mode})...[/bold cyan]")
    await core_context.action_executor.execute("sync.db", write=write)

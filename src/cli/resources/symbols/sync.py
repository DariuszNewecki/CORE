# src/cli/resources/symbols/sync.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("sync")
@command_meta(
    canonical_name="database.sync",
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
    logger.info("[bold cyan]🔄 Synchronizing Symbols to DB (%s)...[/bold cyan]", mode)
    await core_context.action_executor.execute("sync.db", write=write)

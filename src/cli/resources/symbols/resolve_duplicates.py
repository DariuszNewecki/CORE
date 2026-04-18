# src/cli/resources/symbols/resolve_duplicates.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("resolve-duplicates")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: c9ca3aa7-a542-4f3c-bbf3-d8dc97d4400a
async def resolve_symbol_duplicates(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Regenerate conflicting UUIDs."),
):
    """
    Find and resolve duplicate '# ID:' anchors in the codebase.

    If multiple symbols share the same UUID, the older entry is preserved
    and colliding symbols are assigned fresh, unique identifiers.
    """
    core_context: CoreContext = ctx.obj
    mode = "RESOLVING" if write else "ANALYZING"
    logger.info("[bold cyan]👯 %s duplicate ID collisions...[/bold cyan]", mode)
    await core_context.action_executor.execute("fix.duplicate_ids", write=write)

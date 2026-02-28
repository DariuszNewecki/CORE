# src/body/cli/resources/symbols/resolve_duplicates.py
# ID: e17b25b1-d5f5-4d1d-b253-55cec673bb41

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("resolve-duplicates")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 35c377c3-f673-46d0-804b-9d878396d269
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
    console.print(
        f"[bold cyan]\U0001f46f {mode} duplicate ID collisions...[/bold cyan]"
    )

    await core_context.action_executor.execute("fix.duplicate_ids", write=write)

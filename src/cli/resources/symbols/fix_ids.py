# src/cli/resources/symbols/fix_ids.py
import typer
from rich.console import Console

from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("fix-ids")
@command_meta(
    canonical_name="symbols.fix-ids",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Assign stable # ID: anchors to untagged symbols.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 37ac33b4-76d3-40c4-8955-3b81a2a4ccf2
async def fix_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Inject missing UUIDs into source files."
    ),
) -> None:
    """
    Assign stable '# ID:' anchors to all untagged public symbols.

    Scans 'src/' and modifies files to ensure knowledge graph stability.
    """
    core_context: CoreContext = ctx.obj
    if not write:
        console.print("[yellow]📋 Analysis mode: Scanning for missing IDs...[/yellow]")
    else:
        console.print(
            "[bold red]🧪 Applying missing ID anchors to source code...[/bold red]"
        )
    await core_context.action_executor.execute("fix.ids", write=write)

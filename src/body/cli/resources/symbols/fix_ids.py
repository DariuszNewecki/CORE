# src/body/cli/resources/symbols/fix_ids.py
import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("fix-ids")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 888a9a3e-30b1-438d-ac9f-0bcc682d9f09
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

    # Routes to fix.ids atomic action
    await core_context.action_executor.execute("fix.ids", write=write)

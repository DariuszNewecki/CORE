# src/body/cli/resources/vectors/sync.py
import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("sync")
@core_command(requires_context=True, dangerous=True)
# ID: c5b39594-d5ca-4fca-b77b-d054c64c8e08
async def sync_vectors(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes to Qdrant."),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: policies, patterns, or all"
    ),
) -> None:
    """
    Synchronize constitutional documents to vector collections.

    Routes execution through the ActionExecutor for full auditability.
    """
    core_context: CoreContext = ctx.obj

    console.print(
        f"[bold cyan]🧠 Vector Sync Mode:[/bold cyan] {'WRITE' if write else 'DRY-RUN'}"
    )

    # RULE: Delegate to Atomic Actions instead of implementing logic here
    # This ensures the sync is recorded in core.action_results
    result = await core_context.action_executor.execute(
        "sync.vectors.constitution", write=write
    )

    # @core_command handles the display of the ActionResult

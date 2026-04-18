# src/cli/resources/dev/sync.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta
from will.workflows.dev_sync_workflow import DevSyncWorkflow

from .hub import app


console = Console()


@app.command("sync")
@command_meta(
    canonical_name="dev.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Run complete developer synchronization workflow.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: a3cfcc6d-0028-41fe-93d9-c14440a3c75b
async def sync_workflow(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply all fixes and sync state to DB/Vectors."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt for dangerous operations."
    ),
) -> None:
    """
    Run the complete developer synchronization workflow.

    1. Fixes code (IDs, headers, formatting).
    2. Syncs knowledge graph to PostgreSQL.
    3. Syncs semantic vectors to Qdrant.
    """
    core_context = ctx.obj
    mode = "WRITE" if write else "DRY-RUN"
    logger.info("[bold cyan]🔄 Running Dev-Sync Workflow (%s)...[/bold cyan]", mode)
    workflow = DevSyncWorkflow(core_context)
    result = await workflow.run(write=write)
    if result.ok:
        logger.info("\n[bold green]✅ System synchronized successfully.[/bold green]")
    else:
        logger.info("\n[bold red]❌ Sync failed during one or more phases.[/bold red]")

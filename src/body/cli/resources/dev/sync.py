# src/body/cli/resources/dev/sync.py
import typer
from rich.console import Console

from body.workflows.dev_sync_workflow import DevSyncWorkflow
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("sync")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 05c5113b-3613-4b56-be33-c680c6b7e74f
async def sync_workflow(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply all fixes and sync state to DB/Vectors."
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
    console.print(f"[bold cyan]🔄 Running Dev-Sync Workflow ({mode})...[/bold cyan]")

    # The workflow handles the composition of multiple atomic actions
    workflow = DevSyncWorkflow(core_context)
    result = await workflow.run()

    if result.ok:
        console.print("\n[bold green]✅ System synchronized successfully.[/bold green]")
    else:
        console.print(
            "\n[bold red]❌ Sync failed during one or more phases.[/bold red]"
        )

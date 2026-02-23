# src/body/cli/resources/vectors/sync.py

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app  # ← CHANGE: Import from .hub


console = Console()


@app.command("sync")
@core_command(requires_context=True, dangerous=True)
# ID: 0cbd298d-6653-4519-8642-8a82b754b238
async def sync_vectors(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes to Qdrant."),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: policies, patterns, or all"
    ),
) -> None:
    """
    Synchronize constitutional documents to vector collections.
    """
    core_context: CoreContext = ctx.obj
    console.print(
        f"[bold cyan]🧠 Vector Sync (Constitution): {'WRITE' if write else 'DRY-RUN'}[/bold cyan]"
    )

    await core_context.action_executor.execute("sync.vectors.constitution", write=write)

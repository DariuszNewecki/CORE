# src/cli/resources/vectors/sync_code.py

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("sync-code")
@command_meta(
    canonical_name="vectors.sync-code",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize codebase symbol embeddings.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: a9f31fb5-2395-4a71-98c1-6817239c24cb
async def sync_code_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all symbols."
    ),
) -> None:
    """
    Synchronize codebase symbol embeddings with the vector database.
    """
    core_context: CoreContext = ctx.obj
    mode = "SYNCING" if write else "ANALYZING"
    console.print(f"[bold cyan]🧠 {mode} codebase vectors...[/bold cyan]")

    await core_context.action_executor.execute(
        "sync.vectors.code", write=write, force=force
    )

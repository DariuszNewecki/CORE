# src/cli/resources/vectors/sync_code.py
from shared.logger import getLogger


logger = getLogger(__name__)
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
# ID: 6489b6df-f2d8-4480-b0e2-e3054c9c11dc
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
    logger.info("[bold cyan]🧠 %s codebase vectors...[/bold cyan]", mode)
    await core_context.action_executor.execute(
        "sync.vectors.code", write=write, force=force
    )

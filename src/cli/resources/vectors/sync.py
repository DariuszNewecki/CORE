# src/cli/resources/vectors/sync.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("sync")
@command_meta(
    canonical_name="vectors.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize constitutional documents to vector collections.",
    dangerous=True,
)
@core_command(requires_context=True, dangerous=True)
# ID: 558c245a-7663-4a87-bf2d-4e3c612498bd
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
    logger.info(
        "[bold cyan]🧠 Vector Sync (Constitution): %s[/bold cyan]",
        "WRITE" if write else "DRY-RUN",
    )
    await core_context.action_executor.execute("sync.vectors.constitution", write=write)

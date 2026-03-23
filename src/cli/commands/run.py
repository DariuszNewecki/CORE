# src/cli/commands/run.py
"""
Commands for executing specific complex system processes.

Following the V2 Alignment Roadmap, the redundant 'develop' command has
been removed from this group. All autonomous development should now
be initiated via the primary 'develop refactor' command.
"""

from __future__ import annotations

import typer

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles.",
    no_args_is_help=True,
)


@run_app.command("vectorize")
@core_command(dangerous=True)
# ID: f8e9d0a1-b2c3-4d5e-6f7a-8b9c0d1e2f3a
async def vectorize_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, help="Force re-vectorization of all capabilities."
    ),
):
    """
    Vectorize codebase artifacts using the constitutional worker pipeline
    (RepoCrawlerWorker + RepoEmbedderWorker).
    """
    context: CoreContext = ctx.obj

    logger.info("🚀 Starting vectorization via constitutional worker pipeline...")

    await context.action_executor.execute("sync.vectors.code", write=write, force=force)

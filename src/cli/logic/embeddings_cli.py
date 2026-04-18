# src/cli/logic/embeddings_cli.py

"""
CLI wiring for embeddings & vectorization commands.
Exposes: `core-admin knowledge vectorize [--write|--dry-run]`
"""

from __future__ import annotations

import typer

from cli.utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
app = typer.Typer(
    name="knowledge", no_args_is_help=True, help="Knowledge graph & embeddings commands"
)


@app.command("vectorize")
@core_command(dangerous=True)
# ID: bd2d47b7-8dce-4e8c-93bd-0c31d0b13be0
async def vectorize_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Persist vectors to Qdrant."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate only, do not upsert to Qdrant."
    ),
):
    """
    Vectorize codebase artifacts using the constitutional worker pipeline
    (RepoCrawlerWorker + RepoEmbedderWorker).
    """
    context: CoreContext = ctx.obj

    if dry_run:
        write = False

    logger.info("🚀 Starting vectorization via constitutional worker pipeline...")
    await context.action_executor.execute("sync.vectors.code", write=write)

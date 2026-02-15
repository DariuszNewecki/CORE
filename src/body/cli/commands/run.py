# src/body/cli/commands/run.py
# ID: b400e661-52bf-43c3-9b3f-71243d338583
"""
Commands for executing specific complex system processes.

Following the V2 Alignment Roadmap, the redundant 'develop' command has
been removed from this group. All autonomous development should now
be initiated via the primary 'develop refactor' command.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from features.introspection.vectorization_service import run_vectorize
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
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
    # CONSTITUTIONAL FIX: Added write option for consistency with @core_command
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, help="Force re-vectorization of all capabilities."
    ),
):
    """
    Vectorize capabilities in the knowledge base for semantic search.
    """
    context: CoreContext = ctx.obj

    logger.info("🚀 Starting capability vectorization process...")

    # Load environment
    load_dotenv()

    # We open a single session and keep it open for the duration of the task
    async with get_session() as session:
        from shared.infrastructure.config_service import ConfigService

        # 1. Check if LLMs are enabled (Mind-layer state)
        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

        if not llm_enabled:
            logger.error("❌ LLMs must be enabled to generate embeddings.")
            raise typer.Exit(code=1)

        # 2. Execute vectorization (Body-layer action)
        try:
            # Note: run_vectorize takes dry_run, which is !write
            # We pass the open session to ensure it can update the DB correctly
            await run_vectorize(
                context=context, session=session, dry_run=not write, force=force
            )
        except Exception as e:
            logger.error("❌ Orchestration failed: %s", e, exc_info=True)
            raise typer.Exit(code=1)

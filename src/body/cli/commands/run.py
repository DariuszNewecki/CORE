# src/body/cli/commands/run.py
"""
Provides functionality for the run module.
Refactored for A2 Autonomy: Uses ServiceRegistry for Just-In-Time dependency injection.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

# We import the logic function, but we will inject dependencies before calling it
from features.introspection.vectorization_service import run_vectorize
from shared.context import CoreContext
from shared.logger import getLogger
from will.cli_logic.run import _develop

logger = getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


@run_app.command("develop")
# ID: e3a1c5e2-53cd-41d0-b983-a673e0694a48
def develop_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="The high-level development goal for CORE to achieve.",
        show_default=False,
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Path to a file containing the development goal.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
        show_default=False,
    ),
) -> None:
    """Orchestrates the autonomous development process from a high-level goal."""
    core_context: CoreContext = ctx.obj

    # Ensure CognitiveService has Qdrant wired up if it needs it (develop often does for retrieval)
    async def _setup_and_run():
        if core_context.registry:
            # JIT Injection: Ensure CognitiveService has its dependencies
            qdrant = await core_context.registry.get_qdrant_service()
            core_context.cognitive_service._qdrant_service = qdrant
            core_context.qdrant_service = qdrant

        await _develop(context=core_context, goal=goal, from_file=from_file)

    asyncio.run(_setup_and_run())


@run_app.command("vectorize")
# ID: 4ba1c83a-cab2-425b-b9e7-2fd601103c7c
def vectorize_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Persist changes to Qdrant."),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
) -> None:
    """Scan capabilities from the DB, generate embeddings, and upsert to Qdrant."""
    core_context: CoreContext = ctx.obj

    async def _setup_and_vectorize():
        logger.info("Initializing services for vectorization via Registry...")

        # 1. Fetch singleton from Registry (slow import happens here)
        qdrant = await core_context.registry.get_qdrant_service()

        # 2. Wire it into the context and cognitive service
        core_context.qdrant_service = qdrant
        core_context.cognitive_service._qdrant_service = qdrant

        # 3. Run the feature logic
        await run_vectorize(context=core_context, dry_run=not write, force=force)

    asyncio.run(_setup_and_vectorize())

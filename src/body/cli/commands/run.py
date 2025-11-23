# src/body/cli/commands/run.py
"""Provides functionality for the run module."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from shared.context import CoreContext
from shared.logger import getLogger

# --- START OF FIX ---
# Updated import to point to the new 'will' location for the logic file
from will.cli_logic.run import _develop

# --- END OF FIX ---

logger = getLogger(__name__)

run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)

_context: CoreContext | None = None


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
    asyncio.run(_develop(context=core_context, goal=goal, from_file=from_file))


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

    # ✅ Lazy Qdrant initialization: only when this command actually runs
    if core_context.qdrant_service is None:
        from services.clients.qdrant_client import QdrantService

        logger.info(
            "Initializing QdrantService for 'run vectorize' command via core context..."
        )
        core_context.qdrant_service = QdrantService()

    from features.introspection.vectorization_service import run_vectorize

    asyncio.run(run_vectorize(context=core_context, dry_run=not write, force=force))

# src/cli/commands/run.py
"""
Registers and implements the 'run' command group for executing complex,
multi-step processes and autonomous cycles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from cli.logic.run import develop
from features.introspection.vectorization_service import run_vectorize
from shared.context import CoreContext

run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)

# NOTE: We are no longer using a module-level _context or set_context function.


@run_app.command("develop")
# ID: d10d0d34-054c-4923-bda9-1264f6d85813
def develop_command(
    ctx: typer.Context,  # <-- ADD THIS ARGUMENT
    goal: Optional[str] = typer.Argument(
        None,
        help="The high-level development goal for CORE to achieve.",
        show_default=False,
    ),
    from_file: Optional[Path] = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Path to a file containing the development goal.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
        show_default=False,
    ),
):
    """Orchestrates the autonomous development process from a high-level goal."""
    # --- START MODIFICATION ---
    # Get the context directly from the Typer context object. This is the robust way.
    core_context: CoreContext = ctx.obj
    # --- END MODIFICATION ---

    develop(context=core_context, goal=goal, from_file=from_file)


@run_app.command("vectorize")
# ID: 61b0c0e6-41ad-4050-bb23-54d39ef9e248
def vectorize_command(
    ctx: typer.Context,  # <-- ADD THIS ARGUMENT
    write: bool = typer.Option(False, "--write", help="Persist changes to Qdrant."),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
):
    """Scan capabilities from the DB, generate embeddings, and upsert to Qdrant."""
    # --- START MODIFICATION ---
    # Get the context directly from the Typer context object.
    core_context: CoreContext = ctx.obj
    # --- END MODIFICATION ---

    cog = core_context.cognitive_service
    asyncio.run(run_vectorize(cognitive_service=cog, dry_run=not write, force=force))

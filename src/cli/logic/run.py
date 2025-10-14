# src/cli/logic/run.py
"""
Registers and implements the 'run' command group for executing complex,
multi-step processes and autonomous cycles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv

from features.autonomy.autonomous_developer import develop_from_goal
from features.introspection.vectorization_service import run_vectorize
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("core_admin.run")
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


@run_app.command(
    "develop",
    help="Orchestrates the autonomous development process from a high-level goal.",
)
# ID: 1ddfca35-8fcd-4f5e-925d-f0659f34e2a4
def develop(
    context: CoreContext,
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
):
    """Orchestrates the autonomous development process from a high-level goal."""
    if not goal and not from_file:
        log.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)

    if from_file:
        goal_content = from_file.read_text(encoding="utf-8").strip()
    else:
        goal_content = goal.strip()

    load_dotenv()
    if not settings.LLM_ENABLED:
        log.error("❌ The 'develop' command requires LLMs to be enabled.")
        raise typer.Exit(code=1)

    # The CLI now simply calls the dedicated service.
    success, message = asyncio.run(develop_from_goal(context, goal_content))

    if success:
        typer.secho(f"\n✅ Goal execution successful: {message}", fg=typer.colors.GREEN)
        typer.secho(
            "   -> Run 'git status' to see the changes and 'core-admin submit changes' to integrate them.",
            bold=True,
        )
    else:
        typer.secho(f"\n❌ Goal execution failed: {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@run_app.command(
    "vectorize",
    help="Scan capabilities from the DB, generate embeddings, and upsert to Qdrant.",
)
# ID: b6ca020c-68ea-4280-b189-e2e7d453f391
def vectorize_capabilities(
    context: CoreContext,
    dry_run: bool = typer.Option(
        True, "--dry-run/--write", help="Show changes without writing to Qdrant."
    ),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
):
    """The CLI wrapper for the database-driven vectorization process."""
    log.info("🚀 Starting capability vectorization process...")
    if not settings.LLM_ENABLED:
        log.error("❌ LLMs must be enabled to generate embeddings.")
        raise typer.Exit(code=1)
    try:
        cog = context.cognitive_service
        asyncio.run(run_vectorize(cognitive_service=cog, dry_run=dry_run, force=force))
    except Exception as e:
        log.error(f"❌ Orchestration failed: {e}", exc_info=True)
        raise typer.Exit(code=1)

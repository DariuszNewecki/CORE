# src/cli/commands/run.py
"""
Registers and implements the 'run' command group for executing complex,
multi-step processes and autonomous cycles.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from cli.logic.run import develop, vectorize_capabilities
from shared.context import CoreContext

run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)

_context: Optional[CoreContext] = None


@run_app.command("develop")
# ID: d10d0d34-054c-4923-bda9-1264f6d85813
def develop_command(
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
    if not _context:
        raise typer.Exit("Context not set for develop command.")
    develop(context=_context, goal=goal, from_file=from_file)


@run_app.command("vectorize")
# ID: 61b0c0e6-41ad-4050-bb23-54d39ef9e248
def vectorize_command(
    dry_run: bool = typer.Option(
        True, "--dry-run/--write", help="Show changes without writing to Qdrant."
    ),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
):
    """Scan capabilities from the DB, generate embeddings, and upsert to Qdrant."""
    if not _context:
        raise typer.Exit("Context not set for vectorize command.")
    vectorize_capabilities(context=_context, dry_run=dry_run, force=force)

# src/body/cli/logic/tools.py
"""
Registers a 'tools' command group for powerful, operator-focused maintenance tasks.
This is the new, governed home for logic from standalone scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import shared.logger
import typer
from features.maintenance.maintenance_service import rewire_imports

# Import the moved script module
from features.maintenance.scripts import context_export

logger = shared.logger.getLogger(__name__)

tools_app = typer.Typer(
    help="Governed, operator-focused maintenance and refactoring tools."
)


@tools_app.command(
    "rewire-imports",
    help="Run after major refactoring to fix all Python import statements across 'src/'.",
)
# ID: 4d6a0245-20c9-425e-a0cd-a390c8dd063c
def rewire_imports_cli(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
):
    """
    CLI wrapper for the import rewiring service.
    """
    dry_run = not write
    logger.info("Starting architectural import re-wiring script...")
    if dry_run:
        logger.info("DRY RUN MODE: No files will be changed.")
    else:
        logger.info("WRITE MODE: Files will be modified.")

    total_changes = rewire_imports(dry_run=dry_run)

    logger.info("--- Re-wiring Complete ---")
    if dry_run:
        logger.info(f"DRY RUN: Found {total_changes} potential import changes to make.")
        logger.info("Run with '--write' to apply them.")
    else:
        logger.info(f"APPLIED: Made {total_changes} import changes.")

    logger.info("--- NEXT STEPS ---")
    logger.info(
        "1. VERIFY: Run 'make format' and then 'make check' to ensure compliance."
    )


@tools_app.command("export-context")
# ID: af5abbe5-0304-4f54-9eb0-596d71791b41
def export_context_cmd(
    output_dir: Path = typer.Option(
        Path("./scripts/exports"),
        "--output-dir",
        help="Directory to write export bundle into",
    ),
    db_url: str = typer.Option(None, "--db-url", help="Database URL override"),
    qdrant_url: str = typer.Option(None, "--qdrant-url", help="Qdrant URL override"),
    qdrant_collection: str = typer.Option(
        None, "--qdrant-collection", help="Qdrant collection override"
    ),
):
    """
    Export a complete operational snapshot (Mind/Body/State/Vectors).
    Wraps features.maintenance.scripts.context_export.
    """
    # Prepare arguments to look like sys.argv for the existing script logic
    # This avoids rewriting the complex argparse logic inside the script for now.
    args = ["context_export", "--output-dir", str(output_dir)]

    if db_url:
        args.extend(["--db-url", db_url])
    if qdrant_url:
        args.extend(["--qdrant-url", qdrant_url])
    if qdrant_collection:
        args.extend(["--qdrant-collection", qdrant_collection])

    # Patch sys.argv temporarily to invoke the script's main
    original_argv = sys.argv
    try:
        sys.argv = args
        context_export.main()
    except SystemExit as e:
        # The script calls sys.exit(), we catch it to prevent CLI crash
        if e.code != 0:
            raise typer.Exit(e.code)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise typer.Exit(1)
    finally:
        sys.argv = original_argv

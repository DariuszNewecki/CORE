# src/cli/logic/tools.py
"""
Registers a 'tools' command group for powerful, operator-focused maintenance tasks.
This is the new, governed home for logic from standalone scripts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from body.maintenance.maintenance_service import rewire_imports

# Import the moved script module
from body.maintenance.scripts import context_export
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)

tools_app = typer.Typer(
    help="Governed, operator-focused maintenance and refactoring tools."
)


@tools_app.command(
    "rewire-imports",
    help="Run after major refactoring to fix all Python import statements across 'src/'.",
)
@command_meta(
    canonical_name="imports.rewire",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Automatically fixes Python import statements across the codebase after major refactoring.",
    dangerous=True,
)
# ID: 85a8bd02-dba4-4aab-9329-c36cc60a121a
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

    # REFACTORED: Removed direct settings import
    from body.infrastructure.bootstrap import create_core_context
    from body.infrastructure.storage.file_handler import FileHandler
    from body.services.service_registry import service_registry

    context = create_core_context(service_registry)
    file_handler = FileHandler(str(context.git_service.repo_path))
    total_changes = rewire_imports(context, file_handler, dry_run=dry_run)

    logger.info("--- Re-wiring Complete ---")
    if dry_run:
        logger.info(
            "DRY RUN: Found %s potential import changes to make.", total_changes
        )
        logger.info("Run with '--write' to apply them.")
    else:
        logger.info("APPLIED: Made %s import changes.", total_changes)

    logger.info("--- NEXT STEPS ---")
    logger.info(
        "1. VERIFY: Run 'make format' and then 'make check' to ensure compliance."
    )


@tools_app.command("export-context")
@command_meta(
    canonical_name="context.export",
    behavior=CommandBehavior.TRANSFORM,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Exports a complete operational snapshot including Mind, Body, State, and Vector data.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: a09e7c1d-791a-4132-bd51-146e468b8d89
async def export_context_cmd(ctx: typer.Context) -> None:
    """
    Export an operational snapshot into the governed exports directory.

    Runs body.maintenance.scripts.context_export.ContextExporter against the
    CLI's CoreContext. The former --output-dir / --db-url / --qdrant-url /
    --qdrant-collection options were removed: they were forwarded via a
    patched sys.argv that the exporter never parsed, and the exporter's
    coroutine was never awaited, so the command had never run.
    """
    core_context: CoreContext = ctx.obj
    exporter = context_export.ContextExporter(context=core_context)
    export_dir = await exporter.run()
    logger.info("Context export written to %s", export_dir)

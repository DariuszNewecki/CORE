# src/body/cli/commands/enrich.py
"""
Registers the 'enrich' command group.
Refactored to use the Constitutional CLI Framework.
"""

from __future__ import annotations

import typer
from rich.console import Console

from features.self_healing.enrichment_service import enrich_symbols
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session


console = Console()
enrich_app = typer.Typer(help="Autonomous tools to enrich the system's knowledge base.")


@enrich_app.command("symbols")
@core_command(dangerous=True)
# ID: 117c1292-94d7-4e80-9ca2-8385a535bace
async def enrich_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the generated descriptions to the database."
    ),
):
    """Uses an AI agent to write descriptions for symbols that have placeholders."""
    core_context: CoreContext = ctx.obj

    # FIXED: Create session and pass to enrich_symbols
    async with get_session() as session:
        await enrich_symbols(
            session=session,
            cognitive_service=core_context.cognitive_service,
            qdrant_service=core_context.qdrant_service,
            dry_run=not write,
        )

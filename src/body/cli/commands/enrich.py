# src/body/cli/commands/enrich.py
"""
Registers the 'enrich' command group.
"""

from __future__ import annotations

import asyncio

import typer
from features.self_healing.enrichment_service import enrich_symbols
from rich.console import Console
from shared.context import CoreContext

console = Console()
enrich_app = typer.Typer(help="Autonomous tools to enrich the system's knowledge base.")

_context: CoreContext | None = None


@enrich_app.command("symbols")
# ID: 14372f44-7251-4e58-b389-16377460c7be
def enrich_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the generated descriptions to the database."
    ),
):
    """Uses an AI agent to write descriptions for symbols that have placeholders."""
    core_context: CoreContext = ctx.obj
    # CORRECTED: Pass both required services from the context
    asyncio.run(
        enrich_symbols(
            cognitive_service=core_context.cognitive_service,
            qdrant_service=core_context.qdrant_service,
            dry_run=not write,
        )
    )

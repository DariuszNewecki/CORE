# src/cli/commands/enrich.py
"""
Registers the 'enrich' command group.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from features.self_healing.enrichment_service import enrich_symbols
from shared.context import CoreContext

console = Console()
enrich_app = typer.Typer(help="Autonomous tools to enrich the system's knowledge base.")

_context: CoreContext | None = None


@enrich_app.command("symbols")
# ID: 7ecf56f5-c723-45f1-b1a8-4dbb19868968
def enrich_symbols_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the generated descriptions to the database."
    ),
):
    """Uses an AI agent to write descriptions for symbols that have placeholders."""
    if not _context:
        raise typer.Exit("Context not set for enrich symbols command.")
    asyncio.run(enrich_symbols(_context.cognitive_service, dry_run=not write))

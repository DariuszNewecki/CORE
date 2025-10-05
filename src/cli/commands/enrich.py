# src/cli/commands/enrich.py
from __future__ import annotations

import asyncio

import typer
from features.self_healing.enrichment_service import enrich_symbols
from rich.console import Console
from shared.context import CoreContext

console = Console()
enrich_app = typer.Typer(help="Autonomous tools to enrich the system's knowledge base.")


@enrich_app.command("symbols")
# ID: 7ecf56f5-c723-45f1-b1a8-4dbb19868968
def enrich_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the generated descriptions to the database."
    ),
):
    """Uses an AI agent to write descriptions for symbols that have placeholders."""
    core_context: CoreContext = ctx.obj
    asyncio.run(enrich_symbols(core_context.cognitive_service, dry_run=not write))


# ID: 05372cbf-1f9b-45cb-b892-7bf0e6a8ba41
def register(app: typer.Typer, context: CoreContext):
    """Register the 'enrich' command group to the main CLI app."""
    app.add_typer(enrich_app, name="enrich")

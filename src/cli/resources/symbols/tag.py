# src/body/cli/resources/symbols/tag.py
# ID: b1c2d3e4-f5a6-7890-abcd-ef1234567891

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

from .hub import app


console = Console()


@app.command("tag")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: d9e589d3-55e0-4a12-a5b3-08a89ea22717
async def tag_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write suggested tags to the database."
    ),
) -> None:
    """
    Automatically tag untagged capabilities using AI reasoning.

    Consults the TaggerAgent to suggest 'domain.capability' names for
    symbols that currently have 'unassigned' status in the registry.
    """
    from will.self_healing.capability_tagging_service import main_async

    core_context: CoreContext = ctx.obj

    mode = "APPLYING" if write else "PREVIEWING"
    console.print(f"[bold cyan]\U0001f9e0 {mode} AI capability tagging...[/bold cyan]")

    await main_async(
        session_factory=get_session,
        cognitive_service=core_context.cognitive_service,
        knowledge_service=core_context.knowledge_service,
        write=write,
        dry_run=not write,
    )

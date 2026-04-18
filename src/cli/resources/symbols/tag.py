# src/cli/resources/symbols/tag.py
from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

from .hub import app


console = Console()


@app.command("tag")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 7c191977-2cdb-4639-bf03-797ae163b7c5
async def tag_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write suggested tags to the database."
    ),
    limit: int = typer.Option(
        0, "--limit", help="Limit number of symbols to process (0 = all)."
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
    logger.info("[bold cyan]🧠 %s AI capability tagging...[/bold cyan]", mode)
    await main_async(
        session_factory=get_session,
        cognitive_service=core_context.cognitive_service,
        knowledge_service=core_context.knowledge_service,
        write=write,
        dry_run=not write,
        limit=limit,
    )

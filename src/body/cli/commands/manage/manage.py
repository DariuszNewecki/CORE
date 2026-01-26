# src/body/cli/commands/manage/manage.py

"""
Core entry point for the 'manage' command group.
Thin shell redirecting to modular management departments (V2.3).
"""

from __future__ import annotations

import typer
from rich.console import Console

from features.project_lifecycle.definition_service import define_symbols
from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session

from . import (
    db_sub_app,
    dotenv_sub_app,
    keys_sub_app,
    patterns_sub_app,
    policies_sub_app,
    project_sub_app,
    proposals_sub_app,
    vectors_sub_app,
)


console = Console()
manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

# Mount all departmental sub-apps
manage_app.add_typer(db_sub_app, name="database")
manage_app.add_typer(dotenv_sub_app, name="dotenv")
manage_app.add_typer(project_sub_app, name="project")
manage_app.add_typer(proposals_sub_app, name="proposals")
manage_app.add_typer(keys_sub_app, name="keys")
manage_app.add_typer(patterns_sub_app, name="patterns")
manage_app.add_typer(policies_sub_app, name="policies")
manage_app.add_typer(vectors_sub_app, name="vectors")


@manage_app.command("define-symbols")
@core_command(dangerous=True, confirmation=True)
# ID: a55a91c1-4d91-402f-a0fe-721567c39891
async def define_symbols_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Commit defined symbols to database."
    ),
) -> None:
    """CLI entrypoint to run symbol definition across the codebase."""
    if not write:
        console.print(
            "[yellow]Dry run: Symbol definition requires --write to persist changes.[/yellow]"
        )
        return

    # result is an ActionResult from define_symbols
    result = await define_symbols(ctx.obj.context_service, get_session)

    console.print(
        f"[green]✓ Symbol definition complete: {result.data['defined']}/{result.data['attempted']} defined[/green]"
    )

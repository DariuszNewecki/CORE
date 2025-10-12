# src/cli/commands/manage.py
"""
Registers the new, verb-based 'manage' command group with subgroups.
Refactored under dry_by_design to use the canonical context setter.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from cli.logic.byor import initialize_repository
from cli.logic.db import export_data, migrate_db
from cli.logic.new import register as register_new_project
from cli.logic.project_docs import docs as project_docs
from cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from cli.logic.proposals_micro import register as register_micro_proposals
from cli.logic.sync import sync_knowledge_base
from cli.logic.sync_manifest import sync_manifest
from features.governance.key_management_service import keygen
from features.maintenance.dotenv_sync_service import run_dotenv_sync
from features.maintenance.migration_service import run_ssot_migration
from features.project_lifecycle.definition_service import define_new_symbols
from rich.console import Console
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("manage_command")
console = Console()

manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
db_sub_app.command("sync-knowledge")(sync_knowledge_base)
db_sub_app.command("sync-manifest")(sync_manifest)


@db_sub_app.command(
    "migrate-ssot",
    help="One-time data migration from legacy files to the SSOT database.",
)
# ID: 3151802b-97cc-45aa-a4e0-c3bdb0b2e30d
def migrate_ssot_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the migration to the database."
    ),
):
    """CLI wrapper for the SSOT migration service."""
    asyncio.run(run_ssot_migration(dry_run=not write))


manage_app.add_typer(db_sub_app, name="database")

dotenv_sub_app = typer.Typer(
    help="Manage runtime configuration from .env.", no_args_is_help=True
)


@dotenv_sub_app.command(
    "sync",
    help="Sync settings from .env to the database, governed by runtime_requirements.yaml.",
)
# ID: bc1da88a-0fa5-45dc-9d34-57075abbcfcd
def dotenv_sync_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the sync to the database."
    ),
):
    """CLI wrapper for the dotenv sync service."""
    asyncio.run(run_dotenv_sync(dry_run=not write))


manage_app.add_typer(dotenv_sub_app, name="dotenv")

project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)
register_new_project(project_sub_app)
project_sub_app.command("onboard")(initialize_repository)
project_sub_app.command("docs")(project_docs)
manage_app.add_typer(project_sub_app, name="project")

proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.", no_args_is_help=True
)
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)


@proposals_sub_app.command("approve")
# ID: e50e9a6d-3efd-41e5-a472-1ce5d8ad2563
def approve_command_wrapper(
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
):
    """Wrapper to pass CoreContext to the approve logic."""
    if not _context:
        raise typer.Exit("Context not set for approve command.")
    proposals_approve(context=_context, proposal_name=proposal_name)


register_micro_proposals(proposals_sub_app, _context)
manage_app.add_typer(proposals_sub_app, name="proposals")

keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.", no_args_is_help=True
)
keys_sub_app.command("generate")(keygen)
manage_app.add_typer(keys_sub_app, name="keys")


@manage_app.command(
    "define-symbols",
    help="Defines all undefined capabilities one by one using an AI agent.",
)
# ID: 63ef4a80-6f41-4700-8653-64a853a1f279
def define_symbols_command():
    """Synchronous wrapper that calls the refactored definition service."""
    console.print(
        "[bold yellow]Running asynchronous symbol definition...[/bold yellow]"
    )
    if not _context:
        raise typer.Exit("Context not set for define-symbols command.")
    try:
        cognitive_service = _context.cognitive_service
        asyncio.run(define_new_symbols(cognitive_service))
    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred: {e}[/bold red]", highlight=False
        )
        raise typer.Exit(code=1)

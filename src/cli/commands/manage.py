# src/cli/commands/manage.py
"""
Registers the new, verb-based 'manage' command group with subgroups.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from cli.logic.byor import initialize_repository
from cli.logic.db import export_data, migrate_db
from cli.logic.project_docs import docs as project_docs
from cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from cli.logic.proposals_micro import micro_apply, micro_propose
from cli.logic.sync import sync_knowledge_base
from cli.logic.sync_manifest import sync_manifest
from features.governance.key_management_service import keygen
from features.maintenance.dotenv_sync_service import run_dotenv_sync
from features.maintenance.migration_service import run_ssot_migration
from features.project_lifecycle.definition_service import define_new_symbols
from features.project_lifecycle.scaffolding_service import new_project
from rich.console import Console
from shared.context import CoreContext

console = Console()
manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

# NOTE: We are no longer using a module-level _context or set_context function.

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
    asyncio.run(run_dotenv_sync(dry_run=not write))


manage_app.add_typer(dotenv_sub_app, name="dotenv")

project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)
project_sub_app.command("new")(new_project)
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
    ctx: typer.Context,  # <-- ADD THIS
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
):
    core_context: CoreContext = ctx.obj  # <-- ADD THIS
    proposals_approve(context=core_context, proposal_name=proposal_name)


@proposals_sub_app.command("micro-apply")
# ID: 486036d8-0553-4630-9f53-bc02fced4f73
def micro_apply_command(
    ctx: typer.Context,  # <-- ADD THIS
    proposal_path: Path = typer.Argument(..., exists=True),
):
    """Validates and applies a micro-proposal JSON file."""
    core_context: CoreContext = ctx.obj  # <-- ADD THIS
    asyncio.run(micro_apply(context=core_context, proposal_path=proposal_path))


@proposals_sub_app.command("micro-propose")
# ID: 45f5e69d-31f9-41ab-b019-1770136a06ea
def micro_propose_command(
    ctx: typer.Context,  # <-- ADD THIS
    goal: str = typer.Argument(...),
):
    """Generates a micro-proposal for a given goal without applying it."""
    core_context: CoreContext = ctx.obj  # <-- ADD THIS
    asyncio.run(micro_propose(context=core_context, goal=goal))


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
def define_symbols_command(
    ctx: typer.Context,  # <-- ADD THIS
):
    """Synchronous wrapper that calls the refactored definition service."""
    console.print(
        "[bold yellow]Running asynchronous symbol definition...[/bold yellow]"
    )
    core_context: CoreContext = ctx.obj  # <-- ADD THIS
    try:
        cognitive_service = core_context.cognitive_service
        asyncio.run(define_new_symbols(cognitive_service))
    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred: {e}[/bold red]", highlight=False
        )
        raise typer.Exit(code=1)

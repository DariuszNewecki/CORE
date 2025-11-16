# src/body/cli/commands/manage.py
"""
Registers the new, verb-based 'manage' command group with subgroups.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from features.introspection.export_vectors import export_vectors
from features.maintenance.dotenv_sync_service import run_dotenv_sync
from features.maintenance.migration_service import run_ssot_migration
from features.project_lifecycle.definition_service import define_new_symbols
from features.project_lifecycle.scaffolding_service import new_project
from mind.governance.key_management_service import keygen
from rich.console import Console
from shared.context import CoreContext
from will.cli_logic.proposals_micro import micro_apply, micro_propose  # Corrected

# --- START OF FIX ---
# Updated imports to point to the new 'will' location for logic files
from body.cli.logic.byor import initialize_repository
from body.cli.logic.db import export_data, migrate_db
from body.cli.logic.project_docs import docs as project_docs
from body.cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from body.cli.logic.sync import sync_knowledge_base
from body.cli.logic.sync_manifest import sync_manifest

# --- END OF FIX ---

console = Console()
manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

_context: CoreContext | None = None

db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
db_sub_app.command("sync-knowledge")(sync_knowledge_base)
db_sub_app.command("sync-manifest")(sync_manifest)
db_sub_app.command("export-vectors")(export_vectors)


@db_sub_app.command(
    "migrate-ssot",
    help="One-time data migration from legacy files to the SSOT database.",
)
# ID: 7b1dac6e-cd1b-4e58-8ac7-0ee135de3299
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
# ID: a7719186-00f3-4e70-a549-de586bb45e0d
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
# ID: a383c906-9af5-410f-9c92-978ed68625ab
def approve_command_wrapper(
    ctx: typer.Context,
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
):
    core_context: CoreContext = ctx.obj
    proposals_approve(context=core_context, proposal_name=proposal_name)


@proposals_sub_app.command("micro-apply")
# ID: 3c419342-3813-4b2e-9727-86353b8512fd
def micro_apply_command(
    ctx: typer.Context,
    proposal_path: Path = typer.Argument(..., exists=True),
):
    """Validates and applies a micro-proposal JSON file."""
    core_context: CoreContext = ctx.obj
    asyncio.run(micro_apply(context=core_context, proposal_path=proposal_path))


@proposals_sub_app.command("micro-propose")
# ID: 7f70241a-844a-4997-958a-40e9cea8739e
def micro_propose_command(
    ctx: typer.Context,
    goal: str = typer.Argument(...),
):
    """Generates a micro-proposal for a given goal without applying it."""
    core_context: CoreContext = ctx.obj
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
# ID: de8a268e-3358-4a49-a898-982b9e5fa9e2
def define_symbols_command(
    ctx: typer.Context,
):
    """Synchronous wrapper that calls the refactored definition service."""
    console.print(
        "[bold yellow]Running asynchronous symbol definition...[/bold yellow]"
    )
    core_context: CoreContext = ctx.obj
    try:
        cognitive_service = core_context.cognitive_service
        qdrant_service = core_context.qdrant_service
        asyncio.run(define_new_symbols(cognitive_service, qdrant_service))
    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred: {e}[/bold red]", highlight=False
        )
        raise typer.Exit(code=1)

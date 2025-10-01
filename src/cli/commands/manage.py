# src/cli/commands/manage.py
"""Registers the new, verb-based 'manage' command group with subgroups."""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from cli.logic.byor import initialize_repository
from cli.logic.db import export_data, migrate_db
from cli.logic.new import register as register_new_project
from cli.logic.project_docs import docs as project_docs
from cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from cli.logic.proposal_service import set_context as set_proposal_context
from cli.logic.sync import sync_knowledge_base
from cli.logic.sync_manifest import sync_manifest

# --- START OF FIX ---
from core.cognitive_service import CognitiveService
from features.governance.key_management_service import register as register_keygen
from features.project_lifecycle.definition_service import define_new_symbols
from shared.config import settings
from shared.context import CoreContext

console = Console()
# --- END OF FIX ---


manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

# Database subgroup
db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
db_sub_app.command("sync-knowledge")(sync_knowledge_base)
db_sub_app.command("sync-manifest")(sync_manifest)
manage_app.add_typer(db_sub_app, name="database")

# Project subgroup
project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)
register_new_project(project_sub_app)
project_sub_app.command("onboard")(initialize_repository)
project_sub_app.command("docs")(project_docs)
manage_app.add_typer(project_sub_app, name="project")

# Proposals subgroup
proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.", no_args_is_help=True
)
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)
proposals_sub_app.command("approve")(proposals_approve)
manage_app.add_typer(proposals_sub_app, name="proposals")

# Keys subgroup
keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.", no_args_is_help=True
)
register_keygen(keys_sub_app)
manage_app.add_typer(keys_sub_app, name="keys")


# --- START OF FIX ---
@manage_app.command(
    "define-symbols",
    help="[Temporary] Re-run the autonomous symbol definition process.",
)
def define_symbols_command():
    """A temporary command to fix the missing DB commit."""
    console.print("[bold yellow]Running standalone symbol definition...[/bold yellow]")
    cognitive_service = CognitiveService(settings.REPO_PATH)
    asyncio.run(define_new_symbols(cognitive_service))
    console.print("[bold green]Symbol definition complete.[/bold green]")


# --- END OF FIX ---


# ID: ec7405ee-fb7c-424c-8d41-239a77a7a24d
def register(app: typer.Typer, context: CoreContext):
    """Register the 'manage' command group with the main CLI app."""
    set_proposal_context(context)
    app.add_typer(manage_app, name="manage")

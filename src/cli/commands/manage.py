# src/cli/commands/manage.py
"""Registers the new, verb-based 'manage' command group with subgroups."""
from __future__ import annotations

import typer

from cli.logic.byor import initialize_repository
from cli.logic.db import export_data, migrate_db
from cli.logic.new import register as register_new_project

# NEW: project docs wrapper
from cli.logic.project_docs import docs as project_docs
from cli.logic.proposal_service import (
    proposals_approve,
    proposals_list,
    proposals_sign,
)
from cli.logic.proposal_service import set_context as set_proposal_context

# database sync helpers
from cli.logic.sync import sync_knowledge_base  # provides sync-knowledge
from cli.logic.sync_manifest import sync_manifest  # provides sync-manifest
from features.governance.key_management_service import register as register_keygen
from shared.context import CoreContext

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
# NEW: docs command (uses the same generator as your Makefile fallback)
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


# ID: ec7405ee-fb7c-424c-8d41-239a77a7a24d
def register(app: typer.Typer, context: CoreContext):
    """Register the 'manage' command group with the main CLI app."""
    set_proposal_context(context)
    app.add_typer(manage_app, name="manage")

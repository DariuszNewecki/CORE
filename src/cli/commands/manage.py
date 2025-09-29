# src/cli/commands/manage.py
"""Registers the new, verb-based 'manage' command group with subgroups."""
from __future__ import annotations

import typer

from cli.logic.byor import initialize_repository
from cli.logic.db import export_data, migrate_db
from cli.logic.new import register as register_new_project
from cli.logic.proposal_service import proposals_approve, proposals_list, proposals_sign
from features.governance.key_management_service import register as register_keygen

manage_app = typer.Typer(
    help="State-changing administrative tasks for the system.",
    no_args_is_help=True,
)

# --- Subgroup: Database ---
db_sub_app = typer.Typer(
    help="Manage the database schema and data.", no_args_is_help=True
)
db_sub_app.command("migrate")(migrate_db)
db_sub_app.command("export")(export_data)
manage_app.add_typer(db_sub_app, name="database")

# --- Subgroup: Project ---
project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)
register_new_project(project_sub_app)
project_sub_app.command("onboard")(initialize_repository)
manage_app.add_typer(project_sub_app, name="project")

# --- Subgroup: Proposals ---
proposals_sub_app = typer.Typer(
    help="Manage constitutional amendment proposals.", no_args_is_help=True
)
proposals_sub_app.command("list")(proposals_list)
proposals_sub_app.command("sign")(proposals_sign)
proposals_sub_app.command("approve")(proposals_approve)
manage_app.add_typer(proposals_sub_app, name="proposals")

# --- Subgroup: Keys ---
keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.", no_args_is_help=True
)
register_keygen(keys_sub_app)
manage_app.add_typer(keys_sub_app, name="keys")


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
def register(app: typer.Typer):
    """Register the 'manage' command group to the main CLI app."""
    app.add_typer(manage_app, name="manage")

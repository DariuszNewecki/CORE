# src/cli/commands/db.py
"""
Registers the top-level 'db' command group for managing the CORE operational database.
"""
from __future__ import annotations

import typer

from cli.commands.migrate import migrate_db
from cli.commands.status import status
from cli.commands.sync_domains import sync_domains

# --- Main DB Command Group ---
db_app = typer.Typer(
    help="Commands for managing the CORE operational database (migrations, syncs, status)."
)

# Register commands directly
db_app.command("status")(status)
db_app.command("sync-domains")(sync_domains)
db_app.command("migrate")(migrate_db)  # Add the new command


# ID: a2e89177-868c-4a49-9f05-87b9f43f0bfc
def register(app: typer.Typer):
    """Register the 'db' command group with the main CLI app."""
    app.add_typer(db_app, name="db")

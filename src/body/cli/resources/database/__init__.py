# src/body/cli/resources/database/__init__.py
"""
Database resource commands.

Constitutional Alignment:
- Resource: database (PostgreSQL state management)
- Actions: sync, migrate, export, cleanup, status
- No layer exposure, resource-first pattern

Commands:
    core-admin database sync      - Sync schema & seed data
    core-admin database migrate   - Run pending migrations
    core-admin database export    - Export to JSON/SQL
    core-admin database cleanup   - Remove orphaned records
    core-admin database status    - Show DB health metrics
"""

from __future__ import annotations

import typer


app = typer.Typer(
    name="database",
    help="PostgreSQL state management operations",
    no_args_is_help=True,
)

# Register command modules
from . import cleanup, export, migrate, status, sync


__all__ = ["app"]

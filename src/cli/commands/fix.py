# src/cli/commands/fix.py
"""Registers the new, verb-based 'fix' command group."""
from __future__ import annotations

import asyncio

import typer

from cli.logic.fixer import (
    assign_ids_command,
    fix_clarity,
    fix_docstrings,
    fix_headers_cmd,
    fix_line_lengths,
    format_code_wrapper,
)
from features.maintenance.command_sync_service import sync_commands_to_db
from features.self_healing.duplicate_id_service import resolve_duplicate_ids

fix_app = typer.Typer(
    help="Self-healing tools that write changes to the codebase.",
    no_args_is_help=True,
)

fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)(format_code_wrapper)
fix_app.command("docstrings", help="Adds missing docstrings.")(fix_docstrings)
fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)(fix_headers_cmd)
fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)(assign_ids_command)
fix_app.command("line-lengths", help="Refactors files with long lines.")(
    fix_line_lengths
)
fix_app.command("clarity", help="Refactors a file for clarity.")(fix_clarity)


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
# ID: 80f2559a-6249-4da0-8e71-905ac843c266
def sync_db_registry_command():
    """CLI wrapper for the command sync service."""
    from cli.admin_cli import app as main_app

    asyncio.run(sync_commands_to_db(main_app))


@fix_app.command(
    "duplicate-ids", help="Finds and fixes duplicate '# ID:' tags in the codebase."
)
# ID: e2683c72-5884-491b-b334-824a9b88e1d3
def fix_duplicate_ids_command(
    write: bool = typer.Option(False, "--write", help="Apply fixes to source files.")
):
    """CLI wrapper for the duplicate ID resolution service."""
    asyncio.run(resolve_duplicate_ids(dry_run=not write))


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
def register(app: typer.Typer):
    """Register the 'fix' command group to the main CLI app."""
    app.add_typer(fix_app, name="fix")

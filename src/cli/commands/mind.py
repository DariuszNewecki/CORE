# src/cli/commands/mind.py
"""
Registers the new 'mind' command group for managing the Working Mind's SSOT.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import typer

from cli.logic.mind_ssot import run_diff, run_import, run_snapshot, run_verify
from shared.context import CoreContext

mind_app = typer.Typer(
    help="Commands to manage the Working Mind (DB-as-SSOT).",
    no_args_is_help=True,
)


@mind_app.command(
    "snapshot",
    help="Export the database to canonical YAML files in .intent/mind_export/.",
)
def snapshot_command(
    env: Optional[str] = typer.Option(
        None, "--env", help="Environment tag (e.g., 'dev', 'prod')."
    ),
    note: Optional[str] = typer.Option(
        None, "--note", help="A brief note to store with the export manifest."
    ),
):
    """CLI wrapper for the snapshot logic."""
    asyncio.run(run_snapshot(env=env, note=note))


@mind_app.command(
    "diff", help="Compare the live database with the exported YAML files."
)
def diff_command(
    as_json: bool = typer.Option(
        False, "--json", help="Output the diff in machine-readable JSON format."
    ),
):
    """CLI wrapper for the diff logic."""
    asyncio.run(run_diff(as_json=as_json))


@mind_app.command(
    "import", help="Import the exported YAML files into the database (idempotent)."
)
def import_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the import to the database."
    ),
):
    """CLI wrapper for the import logic."""
    # This now correctly passes the opposite of 'write' to the 'dry_run' parameter.
    asyncio.run(run_import(dry_run=not write))


@mind_app.command(
    "verify", help="Recomputes digests for exported files and fails on mismatch."
)
def verify_command():
    """CLI wrapper for the verification logic."""
    if not run_verify():
        raise typer.Exit(code=1)


def register(app: typer.Typer, context: CoreContext):
    """Register the 'mind' command group to the main CLI app."""
    app.add_typer(mind_app, name="mind")

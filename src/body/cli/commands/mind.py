# src/body/cli/commands/mind.py
"""
Registers the new 'mind' command group for managing the Working Mind's SSOT.
"""

from __future__ import annotations

import asyncio

import typer

from body.cli.logic.knowledge_sync import run_diff, run_import, run_snapshot, run_verify

mind_app = typer.Typer(
    help="Commands to manage the Working Mind (DB-as-SSOT).", no_args_is_help=True
)


@mind_app.command(
    "snapshot",
    help="Export the database to canonical YAML files in .intent/mind_export/.",
)
# ID: 92cdf207-d8c3-4665-a520-ddbd3714882b
def snapshot_command(
    env: str | None = typer.Option(
        None, "--env", help="Environment tag (e.g., 'dev', 'prod')."
    ),
    note: str | None = typer.Option(
        None, "--note", help="A brief note to store with the export manifest."
    ),
):
    """CLI wrapper for the snapshot logic."""
    asyncio.run(run_snapshot(env=env, note=note))


@mind_app.command(
    "diff", help="Compare the live database with the exported YAML files."
)
# ID: 818e271e-8878-429a-ac31-156f8902893e
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
# ID: 661dded5-1fc8-4bff-a6b3-8912e937595d
def import_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the import to the database."
    ),
):
    """CLI wrapper for the import logic."""
    asyncio.run(run_import(dry_run=not write))


@mind_app.command(
    "verify", help="Recomputes digests for exported files and fails on mismatch."
)
# ID: a1118547-c161-471f-9113-f15259a3be05
def verify_command():
    """CLI wrapper for the verification logic."""
    if not run_verify():
        raise typer.Exit(code=1)

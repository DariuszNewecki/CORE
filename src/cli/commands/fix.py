# src/cli/commands/fix.py
"""Registers the new, verb-based 'fix' command group."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from features.maintenance.command_sync_service import sync_commands_to_db
from features.self_healing.capability_tagging_service import (
    tag_unassigned_capabilities,
)
from features.self_healing.clarity_service import fix_clarity
from features.self_healing.code_style_service import format_code
from features.self_healing.complexity_service import complexity_outliers
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.duplicate_id_service import resolve_duplicate_ids
from features.self_healing.header_service import _run_header_fix_cycle
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.linelength_service import fix_line_lengths
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from rich.console import Console
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("core_admin.fix")
console = Console()
fix_app = typer.Typer(
    help="Self-healing tools that write changes to the codebase.",
    no_args_is_help=True,
)


@fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)
def format_code_wrapper():
    """Wrapper that calls the dedicated code style service."""
    format_code()


@fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)
def fix_headers_cmd(
    file_path: Optional[Path] = None,
    write: bool = False,
):
    """User-friendly wrapper for the header fixing logic."""
    dry_run = not write
    REPO_ROOT = settings.REPO_PATH
    files_to_process = []
    if file_path:
        log.info(f"🎯 Targeting a single file for header fixing: {file_path}")
        files_to_process.append(str(file_path.relative_to(REPO_ROOT)))
    else:
        log.info("Scanning all Python files in the 'src' directory...")
        src_dir = REPO_ROOT / "src"
        all_py_files = src_dir.rglob("*.py")
        files_to_process = sorted([str(p.relative_to(REPO_ROOT)) for p in all_py_files])

    _run_header_fix_cycle(dry_run, files_to_process)


fix_app.command("docstrings", help="Adds missing docstrings.")(fix_docstrings)
fix_app.command("line-lengths", help="Refactors files with long lines.")(
    fix_line_lengths
)
fix_app.command("clarity", help="Refactors a file for clarity.")(fix_clarity)


@fix_app.command("complexity")
def complexity_command(
    file_path: Path = typer.Argument(
        ...,
        help="The path to a specific file to refactor for complexity.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
):
    """Identifies and refactors complexity outliers to improve separation of concerns."""
    complexity_outliers(file_path=file_path, dry_run=not write)


@fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
def assign_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
):
    """CLI wrapper for the symbol ID tagging service."""
    dry_run = not write
    total_assigned = assign_missing_ids(dry_run=dry_run)

    console.print("\n--- ID Assignment Complete ---")
    if total_assigned == 0 and not dry_run:
        console.print("[bold green]✅ No new IDs were needed.[/bold green]")
        return

    if dry_run:
        console.print(
            f"💧 DRY RUN: Found {total_assigned} public symbols that need an ID."
        )
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully assigned {total_assigned} new IDs.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )


@fix_app.command(
    "purge-legacy-tags", help="Removes obsolete '# CAPABILITY:' tags from source code."
)
def purge_legacy_tags_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
):
    """CLI wrapper for the legacy tag purging service."""
    dry_run = not write
    total_removed = purge_legacy_tags(dry_run=dry_run)

    console.print("\n--- Purge Complete ---")
    if dry_run:
        console.print(f"💧 DRY RUN: Found {total_removed} total legacy tags to remove.")
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully removed {total_removed} legacy tags.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )


@fix_app.command(
    "policy-ids", help="Adds a unique `policy_id` UUID to any policy file missing one."
)
def fix_policy_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
):
    """CLI wrapper for the policy ID migration service."""
    dry_run = not write
    total_updated = add_missing_policy_ids(dry_run=dry_run)

    console.print("\n--- Policy ID Migration Complete ---")
    if dry_run:
        console.print(f"💧 DRY RUN: Found {total_updated} policies that need a UUID.")
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully updated {total_updated} policies.")
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin check audit' to verify constitutional compliance."
        )


@fix_app.command(
    "tags",
    help="Use an AI agent to suggest and apply capability tags to untagged symbols.",
)
def fix_tags_command(
    ctx: typer.Context,
    file_path: Optional[Path] = typer.Argument(
        None,
        help="Optional: A specific file to process. If omitted, all files are scanned.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the suggested tags directly to the files."
    ),
):
    """Wrapper for the CapabilityTaggerAgent that writes to the database."""
    core_context: CoreContext = ctx.obj
    tag_unassigned_capabilities(
        cognitive_service=core_context.cognitive_service,
        knowledge_service=core_context.knowledge_service,
        file_path=file_path,
        write=write,
    )


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
    write: bool = typer.Option(False, "--write", help="Apply fixes to source files."),
):
    """CLI wrapper for the duplicate ID resolution service."""
    asyncio.run(resolve_duplicate_ids(dry_run=not write))


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
def register(app: typer.Typer, context: CoreContext):
    """Register the 'fix' command group to the main CLI app."""
    app.add_typer(fix_app, name="fix")

# src/body/cli/commands/fix/metadata.py
"""
Metadata-related self-healing commands for the 'fix' CLI group.

Provides:
- fix ids
- fix purge-legacy-tags
- fix policy-ids
- fix tags
- fix duplicate-ids
"""

from __future__ import annotations

from pathlib import Path

import typer

# NOTE: The old sync wrapper `tag_unassigned_capabilities` was removed.
# We now import the new async entry point directly.
from features.self_healing.capability_tagging_service import (
    main_async as tag_capabilities_async,
)
from features.self_healing.duplicate_id_service import resolve_duplicate_ids
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from shared.cli_utils import async_command
from shared.context import CoreContext

from . import (
    _confirm_dangerous_operation,
    _run_with_progress,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
@handle_command_errors
# ID: b6a55ee8-fce6-48dc-8940-24e9498bbe70
def assign_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    if not _confirm_dangerous_operation("ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    total_assigned = _run_with_progress(
        "Assigning missing IDs", lambda: assign_missing_ids(dry_run=not write)
    )
    console.print(f"[green]Total IDs assigned: {total_assigned}[/green]")


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete '# CAPABILITY:' tags from source code.",
)
@handle_command_errors
# ID: df0742ef-5cc1-4c3f-b885-3c82ef00e08c
def purge_legacy_tags_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    if not _confirm_dangerous_operation("purge-legacy-tags", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    total_removed = _run_with_progress(
        "Purging legacy tags", lambda: purge_legacy_tags(dry_run=not write)
    )
    console.print(f"[green]Total legacy tags removed: {total_removed}[/green]")


@fix_app.command(
    "policy-ids", help="Adds a unique `policy_id` UUID to any policy file missing one."
)
@handle_command_errors
# ID: d6c3eef7-85e2-4be0-b2eb-7aa450eeb81b
def fix_policy_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    if not _confirm_dangerous_operation("policy-ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    total_updated = _run_with_progress(
        "Adding missing policy IDs", lambda: add_missing_policy_ids(dry_run=not write)
    )
    console.print(f"[green]Total policy files updated: {total_updated}[/green]")


@fix_app.command(
    "tags",
    help="Use an AI agent to suggest and apply capability tags to untagged symbols.",
)
@handle_command_errors
@async_command
# ID: d06f24c4-1f52-4f3e-8e7f-e14861098084
async def fix_tags_command(
    ctx: typer.Context,
    file_path: Path | None = typer.Argument(
        None,
        help="Optional: A specific file to process.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the suggested tags directly to the files."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be tagged without writing."
    ),
) -> None:
    if not _confirm_dangerous_operation("tags", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    core_context: CoreContext = ctx.obj
    effective_dry_run = dry_run or not write

    target_files = f"file {file_path}" if file_path else "all files"
    with console.status(f"[cyan]Tagging capabilities in {target_files}...[/cyan]"):
        await tag_capabilities_async(
            write=write,
            dry_run=effective_dry_run,
        )
    console.print("[green]Capability tagging completed[/green]")


@fix_app.command(
    "duplicate-ids", help="Finds and fixes duplicate '# ID:' tags in the codebase."
)
@handle_command_errors
@async_command
# ID: 277119a4-b01c-4237-bfce-f7dcd2b1c10a
async def fix_duplicate_ids_command(
    write: bool = typer.Option(False, "--write", help="Apply fixes to source files."),
) -> None:
    if not _confirm_dangerous_operation("duplicate-ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    with console.status("[cyan]Resolving duplicate IDs...[/cyan]"):
        await resolve_duplicate_ids(dry_run=not write)
    console.print("[green]Duplicate ID resolution completed[/green]")

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

import time
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
from shared.action_types import (
    ActionImpact,
    ActionResult,
)

# CHANGED: Import from action_types
from shared.atomic_action import atomic_action  # NEW: Import decorator
from shared.cli_utils import async_command
from shared.context import CoreContext

from . import (
    _confirm_dangerous_operation,
    console,
    fix_app,
    handle_command_errors,
)


# ID: fix_ids_internal_v1
@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
)
# ID: 61377f91-d017-4749-a863-774ea5c2df3d
async def fix_ids_internal(write: bool = False) -> ActionResult:
    """
    Core logic for fix ids command.

    Assigns stable UUID identifiers to all public symbols (functions, classes)
    that don't already have one. This enables:
    - Stable references across refactorings
    - Symbol tracking in knowledge graph
    - Constitutional governance of code structure

    Args:
        write: If True, apply changes. If False, dry-run only.

    Returns:
        ActionResult with:
        - ok: True if successful
        - data: {"ids_assigned": int, "dry_run": bool, "mode": str}
        - duration_sec: Execution time
    """
    start_time = time.time()

    try:
        total_assigned = assign_missing_ids(dry_run=not write)

        return ActionResult(
            action_id="fix.ids",
            ok=True,
            data={
                "ids_assigned": total_assigned,
                "dry_run": not write,
                "mode": "write" if write else "dry-run",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA,
        )

    except Exception as e:
        return ActionResult(
            action_id="fix.ids",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during ID assignment: {e}"],
        )


@fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
@handle_command_errors
@async_command
# ID: b6a55ee8-fce6-48dc-8940-24e9498bbe70
async def assign_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    """
    CLI wrapper for fix ids command.

    Handles user interaction and presentation while fix_ids_internal()
    contains the core logic. This separation enables:
    - Testing without CLI
    - Workflow orchestration
    - Constitutional governance
    """

    if not _confirm_dangerous_operation("ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    # Call internal function
    with console.status("[cyan]Assigning missing IDs...[/cyan]"):
        result = await fix_ids_internal(write=write)

    # Present results
    if result.ok:
        count = result.data["ids_assigned"]
        mode = result.data["mode"]
        console.print(f"[bold green]Total IDs assigned: {count} ({mode})[/bold green]")
    else:
        error = result.data.get("error", "Unknown error")
        console.print(f"[bold red]Error: {error}[/bold red]")


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete tag formats (e.g. old 'Tag:' or 'Metadata:' lines).",
)
@handle_command_errors
@async_command
# ID: 68f2fc74-f7a5-44fc-9c2a-fc98d8e1ad9f
async def purge_legacy_tags_command(
    write: bool = typer.Option(
        False, "--write", help="Apply changes (remove the lines)."
    ),
) -> None:
    """Remove obsolete tag formats from Python files."""
    if not _confirm_dangerous_operation("purge-legacy-tags", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    removed_count = purge_legacy_tags(dry_run=not write)
    mode = "removed" if write else "would be removed (dry-run)"
    console.print(f"[bold green]Obsolete tags {mode}: {removed_count}[/bold green]")


@fix_app.command(
    "policy-ids",
    help="Assigns missing IDs to policy files in .intent/charter/policies/.",
)
@handle_command_errors
@async_command
# ID: 86a8df48-a3b2-4aa2-9088-61ed36b89c0f
async def fix_policy_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Write the IDs to the policy files."
    ),
    policies_dir: Path = typer.Option(
        Path(".intent/charter/policies"),
        help="Path to the policies directory.",
    ),
) -> None:
    """Ensure each policy file has a unique policy_id."""
    if not _confirm_dangerous_operation("policy-ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    added, skipped = add_missing_policy_ids(
        policies_dir=policies_dir, dry_run=not write
    )
    mode = "write" if write else "dry-run"
    console.print(
        f"[bold green]Policy IDs: added={added}, skipped={skipped} ({mode})[/bold green]"
    )


@fix_app.command(
    "tags",
    help="Tags untagged capabilities by calling the capability-tagging service.",
)
@handle_command_errors
@async_command
# ID: a74fc4e1-b64d-44d9-9ba9-c8f9f9c6d6a7
async def fix_tags_command(
    write: bool = typer.Option(False, "--write", help="Write capability tags to DB."),
) -> None:
    """
    Automatically tag untagged capabilities using the AI naming agent.
    Preserves user-defined tags and only tags capabilities missing them.
    """
    if not _confirm_dangerous_operation("tags", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    ctx = CoreContext.get_or_fail()
    await tag_capabilities_async(write=write, db=ctx.db)


@fix_app.command(
    "duplicate-ids",
    help="Resolves duplicate IDs by regenerating fresh UUIDs for conflicts.",
)
@handle_command_errors
@async_command
# ID: c2a7e1f3-4b9d-4e8a-9c3a-8f5e6d7c8b9a
async def fix_duplicate_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to resolve duplicate IDs."
    ),
) -> None:
    """Detect and resolve duplicate IDs in Python files."""
    if not _confirm_dangerous_operation("duplicate-ids", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    resolved_count = resolve_duplicate_ids(dry_run=not write)
    mode = "resolved" if write else "would be resolved (dry-run)"
    console.print(f"[bold green]Duplicate IDs {mode}: {resolved_count}[/bold green]")

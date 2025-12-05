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
from services.database.session_manager import get_session
from shared.action_types import (
    ActionImpact,
    ActionResult,
)

# CHANGED: Import core_command instead of async_command
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.context import CoreContext

from . import (
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
@core_command(dangerous=True, confirmation=False)
@atomic_action(
    action_id="fix.ids_cmd",
    intent="CLI wrapper for stable UUID assignment to public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification", "atomic_actions"],
    category="fixers",
)
# Note: confirmation=False because IDs are low-risk and essential for system health.
# ID: 6c95448b-f539-4f22-9f44-51052ab5f51e
async def assign_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix ids command.
    """
    # @core_command handles the async loop and safety checks.
    # We return the ActionResult so the framework can print the standard success message.
    with console.status("[cyan]Assigning missing IDs...[/cyan]"):
        return await fix_ids_internal(write=write)


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete tag formats (e.g. old 'Tag:' or 'Metadata:' lines).",
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: c7d68d69-bfaa-477c-a2f8-2d5a5457906a
async def purge_legacy_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes (remove the lines)."
    ),
) -> None:
    """Remove obsolete tag formats from Python files."""
    # Logic preserved, but manual confirmation check removed (handled by decorator)
    removed_count = purge_legacy_tags(dry_run=not write)

    mode = "removed" if write else "would be removed (dry-run)"
    console.print(f"[bold green]Obsolete tags {mode}: {removed_count}[/bold green]")


@fix_app.command(
    "policy-ids",
    help="Assigns missing IDs to policy files in .intent/charter/policies/.",
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: 31c08316-abc6-49ba-babd-938dfc0cdb09
async def fix_policy_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write the IDs to the policy files."
    ),
    policies_dir: Path = typer.Option(
        Path(".intent/charter/policies"),
        help="Path to the policies directory.",
    ),
) -> None:
    """Ensure each policy file has a unique policy_id."""
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
@core_command(dangerous=True, confirmation=True)
# ID: 54686122-b1d1-44a3-8aa6-20daacc94e01
async def fix_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Write capability tags to DB."),
) -> None:
    """
    Automatically tag untagged capabilities using the AI naming agent.
    """
    # Dependency Injection via Framework
    core_context: CoreContext = ctx.obj

    # Call service using new architecture (injecting session factory)
    await tag_capabilities_async(
        session_factory=get_session,
        cognitive_service=core_context.cognitive_service,
        knowledge_service=core_context.knowledge_service,
        write=write,
        dry_run=not write,
    )


@fix_app.command(
    "duplicate-ids",
    help="Resolves duplicate IDs by regenerating fresh UUIDs for conflicts.",
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: 57c9e35a-4813-421f-89e5-7e0ef736efc2
async def fix_duplicate_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to resolve duplicate IDs."
    ),
) -> None:
    """Detect and resolve duplicate IDs in Python files."""
    resolved = resolve_duplicate_ids(dry_run=not write)

    if resolved == 0:
        console.print("[green]✅ No duplicate IDs found[/green]")
    else:
        mode = "resolved" if write else "would be resolved (dry-run)"
        console.print(f"[bold green]Duplicate IDs {mode}: {resolved}[/bold green]")

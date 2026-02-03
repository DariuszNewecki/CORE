# src/body/cli/commands/fix/metadata.py
"""
Metadata-related self-healing commands for the 'fix' CLI group.

Provides:
- fix ids (Assign stable UUIDs)
- fix purge-legacy-tags
- fix policy-ids
- fix tags (Capability tagging)
- fix duplicate-ids
- fix placeholders

CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Orchestrates metadata health via governed atomic actions.
"""

from __future__ import annotations

import time
from pathlib import Path

import typer

from body.atomic.executor import ActionExecutor
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
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

# We only import the App and Console from the local hub
from . import (
    console,
    fix_app,
)


@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
)
# ID: 61377f91-d017-4749-a863-774ea5c2df3d
async def fix_ids_internal(context: CoreContext, write: bool = False) -> ActionResult:
    """
    Core logic for fix ids command. Now uses governed ActionExecutor.
    """
    start_time = time.time()

    try:
        total_assigned = await assign_missing_ids(context, write=write)

        return ActionResult(
            action_id="fix.ids",
            ok=True,
            data={
                "ids_assigned": total_assigned,
                "files_processed": 1 if total_assigned > 0 else 0,
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


@atomic_action(
    action_id="fix.duplicate_ids",
    intent="Resolve duplicate ID conflicts by regenerating UUIDs",
    impact=ActionImpact.WRITE_METADATA,
    policies=["id_uniqueness_check"],
    category="fixers",
)
# ID: 60d8c8e6-6c3a-46cb-91ca-a0a399b5c5d3
async def fix_duplicate_ids_internal(
    context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Core logic for fixing duplicate IDs via governed ActionExecutor.
    """
    start_time = time.time()
    try:
        async with get_session() as session:
            resolved_count = await resolve_duplicate_ids(
                context, session, dry_run=not write
            )

        return ActionResult(
            action_id="fix.duplicate_ids",
            ok=True,
            data={
                "resolved_count": resolved_count,
                "mode": "write" if write else "dry-run",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.duplicate_ids",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start_time,
            logs=[f"Error resolving duplicates: {e}"],
        )


@fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
@core_command(dangerous=True, confirmation=False)
# ID: 444bd442-cc5b-4f7a-a3d4-392ccf86e7be
@atomic_action(
    action_id="assign.ids",
    intent="Atomic action for assign_ids_command",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: e2d50b4f-e3cf-49d3-9f32-476970e8d31f
async def assign_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix ids command.
    """
    with console.status("[cyan]Assigning missing IDs...[/cyan]"):
        return await fix_ids_internal(ctx.obj, write=write)


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete tag formats (e.g. old 'Tag:' or 'Metadata:' lines).",
)
@core_command(dangerous=True, confirmation=True)
# ID: c7d68d69-bfaa-477c-a2f8-2d5a5457906a
async def purge_legacy_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes (remove the lines)."
    ),
) -> None:
    """Remove obsolete tag formats from Python files."""
    removed_count = await purge_legacy_tags(ctx.obj, dry_run=not write)

    mode = "removed" if write else "would be removed (dry-run)"
    console.print(f"[bold green]Obsolete tags {mode}: {removed_count}[/bold green]")


@fix_app.command(
    "policy-ids",
    help="Assigns missing IDs to policy files in .intent/policies/.",
)
@core_command(dangerous=True, confirmation=True)
# ID: 31c08316-abc6-49ba-babd-938dfc0cdb09
async def fix_policy_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write the IDs to the policy files."
    ),
    policies_dir: Path = typer.Option(
        Path(".intent/policies"),
        help="Path to the policies directory.",
    ),
) -> None:
    """Ensure each policy file has a unique policy_id."""
    added, skipped = await add_missing_policy_ids(ctx.obj, dry_run=not write)

    mode = "write" if write else "dry-run"
    console.print(
        f"[bold green]Policy IDs: added={added}, skipped={skipped} ({mode})[/bold green]"
    )


@fix_app.command(
    "tags",
    help="Tags untagged capabilities by calling the capability-tagging service.",
)
@core_command(dangerous=True, confirmation=True)
# ID: 54686122-b1d1-44a3-8aa6-20daacc94e01
async def fix_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Write capability tags to DB."),
) -> None:
    """
    Automatically tag untagged capabilities using the AI naming agent.
    """
    core_context: CoreContext = ctx.obj

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
@core_command(dangerous=True, confirmation=True)
# ID: 57c9e35a-4813-421f-89e5-7e0ef736efc2
@atomic_action(
    action_id="fix.duplicate",
    intent="Atomic action for fix_duplicate_ids_command",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 476a84c1-c2b5-45d9-a7bf-65d297549495
async def fix_duplicate_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to resolve duplicate IDs."
    ),
) -> ActionResult:
    """Detect and resolve duplicate IDs in Python files."""

    with console.status("[cyan]Resolving duplicate IDs...[/cyan]"):
        return await fix_duplicate_ids_internal(ctx.obj, write=write)


@fix_app.command(
    "placeholders",
    help="Automated replacement of forbidden placeholders (FUTURE, pending, none).",
)
@core_command(dangerous=True, confirmation=True)
# ID: b1c2d3e4-f5a6-7890-abcd-ef1234567890
@atomic_action(
    action_id="fix.placeholders",
    intent="Atomic action for fix_placeholders_command",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: bf4ec2e4-67c6-46d4-b8dd-b12155b53339
async def fix_placeholders_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to resolve forbidden placeholders."
    ),
) -> ActionResult:
    """
    Detects and resolves forbidden placeholder strings (pending, FUTURE, etc.)
    using the governed ActionExecutor to ensure compliance with purity standards.
    """
    with console.status("[cyan]Purging forbidden placeholders...[/cyan]"):
        executor = ActionExecutor(ctx.obj)
        return await executor.execute("fix.placeholders", write=write)


@fix_app.command(
    "dead-code", help="Mechanically remove unused variables/functions found by Vulture."
)
@core_command(dangerous=True)
# ID: 3e2f4d95-02db-4f55-9fdb-9e55f9a9d918
async def fix_dead_code_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply the deletions."),
):
    """CLI wrapper for the Vulture Healer."""
    from features.self_healing.vulture_healer import heal_dead_code

    with console.status("[bold cyan]Snipping dead code scars...[/bold cyan]"):
        await heal_dead_code(ctx.obj, write=write)

    if not write:
        console.print(
            "\n[yellow]💡 Dry run complete. Use --write to apply the 'Scissors'.[/yellow]"
        )

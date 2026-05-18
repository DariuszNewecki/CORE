# src/cli/commands/fix/metadata.py
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

from shared.logger import getLogger


logger = getLogger(__name__)
from pathlib import Path

import typer

from body.atomic.executor import ActionExecutor

# DEPRECATED: fix_duplicate_ids_internal moved to
# body/self_healing/duplicate_id_service.py under ADR-050. This re-export
# keeps in-CLI callers working; remove after the CLI migration epic completes.
from body.self_healing.duplicate_id_service import fix_duplicate_ids_internal

# DEPRECATED: fix_ids_internal moved to body/self_healing/id_tagging_service.py
# under ADR-050. This re-export keeps in-CLI callers working; remove after the
# CLI migration epic completes.
from body.self_healing.id_tagging_service import fix_ids_internal
from body.self_healing.policy_id_service import add_missing_policy_ids
from body.self_healing.purge_legacy_tags_service import purge_legacy_tags
from cli.utils import core_command
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from will.self_healing.capability_tagging_service import (
    main_async as tag_capabilities_async,
)

from . import fix_app


__all__ = [
    "fix_dead_code_cmd",
    "fix_duplicate_ids_command",
    "fix_duplicate_ids_internal",
    "fix_ids_internal",
    "fix_placeholders_command",
    "fix_policy_ids_command",
    "fix_tags_command",
    "purge_legacy_tags_command",
]


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete tag formats (e.g. old 'Tag:' or 'Metadata:' lines).",
)
@core_command(dangerous=True, confirmation=True)
# ID: ab1c0d74-ec6c-45b4-a909-2a43eb9b8d41
async def purge_legacy_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes (remove the lines)."
    ),
) -> None:
    """Remove obsolete tag formats from Python files."""
    removed_count = await purge_legacy_tags(ctx.obj, dry_run=not write)
    mode = "removed" if write else "would be removed (dry-run)"
    logger.info("[bold green]Obsolete tags %s: %s[/bold green]", mode, removed_count)


@fix_app.command(
    "policy-ids", help="Assigns missing IDs to policy files in .intent/policies/."
)
@core_command(dangerous=True, confirmation=True)
# ID: d17af23d-3b5a-4372-bf6a-efeef7f15c03
async def fix_policy_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write the IDs to the policy files."
    ),
    policies_dir: Path = typer.Option(
        Path(".intent/policies"), help="Path to the policies directory."
    ),
) -> None:
    """Ensure each policy file has a unique policy_id."""
    added, skipped = await add_missing_policy_ids(ctx.obj, dry_run=not write)
    mode = "write" if write else "dry-run"
    logger.info(
        "[bold green]Policy IDs: added=%s, skipped=%s (%s)[/bold green]",
        added,
        skipped,
        mode,
    )


@fix_app.command(
    "tags", help="Tags untagged capabilities by calling the capability-tagging service."
)
@core_command(dangerous=True, confirmation=True)
# ID: 7d415daf-34de-4971-be89-991cd9490591
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
@atomic_action(
    action_id="fix.duplicate",
    intent="Atomic action for fix_duplicate_ids_command",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 96717df8-d28f-4124-bc1e-71bf3921b358
async def fix_duplicate_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to resolve duplicate IDs."
    ),
) -> ActionResult:
    """Detect and resolve duplicate IDs in Python files."""
    with logger.info("[cyan]Resolving duplicate IDs...[/cyan]"):
        return await fix_duplicate_ids_internal(ctx.obj, write=write)


@fix_app.command(
    "placeholders",
    help="Automated replacement of forbidden placeholders (FUTURE, pending, none).",
)
@core_command(dangerous=True, confirmation=True)
@atomic_action(
    action_id="fix.placeholders",
    intent="Atomic action for fix_placeholders_command",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: e8c8f803-1cad-4150-9e66-e50859d8bd35
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
    with logger.info("[cyan]Purging forbidden placeholders...[/cyan]"):
        executor = ActionExecutor(ctx.obj)
        return await executor.execute("fix.placeholders", write=write)


@fix_app.command(
    "dead-code", help="Mechanically remove unused variables/functions found by Vulture."
)
@core_command(dangerous=True)
# ID: d2a428ee-63c2-4212-8c73-5bbebf514ff0
async def fix_dead_code_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply the deletions."),
):
    """CLI wrapper for the Vulture Healer."""
    from body.self_healing.vulture_healer import heal_dead_code

    with logger.info("[bold cyan]Snipping dead code scars...[/bold cyan]"):
        await heal_dead_code(ctx.obj, write=write)
    if not write:
        logger.info(
            "\n[yellow]💡 Dry run complete. Use --write to apply the 'Scissors'.[/yellow]"
        )

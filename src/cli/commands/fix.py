# src/cli/commands/fix.py
"""
Registers the 'fix' command group.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

# --- START MODIFICATION ---
from cli.logic.proposals_micro import micro_propose, propose_and_apply_autonomously

# --- END MODIFICATION ---
from features.maintenance.command_sync_service import sync_commands_to_db
from features.self_healing.capability_tagging_service import (
    tag_unassigned_capabilities,
)
from features.self_healing.clarity_service import fix_clarity
from features.self_healing.code_style_service import format_code
from features.self_healing.complexity_service import complexity_outliers
from features.self_healing.duplicate_id_service import resolve_duplicate_ids
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.linelength_service import fix_line_lengths
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.prune_orphaned_vectors import (
    main_sync as prune_orphaned_vectors,
)
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from rich.console import Console
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger("core_admin.fix")
console = Console()
fix_app = typer.Typer(
    help="Self-healing tools that write changes to the codebase.",
    no_args_is_help=True,
)

_context: Optional[CoreContext] = None


# ID: 72a4d691-f7c3-4752-bc6a-a08dad2df1dc
def set_context(context: CoreContext) -> None:
    """Sets the shared context for commands in this group."""
    global _context
    _context = context


def _ensure_context() -> CoreContext:
    """Raises a clear error if context is not set."""
    if not _context:
        console.print("[red]Error: Context not initialized.[/red]")
        raise typer.Exit(code=1)
    return _context


def _print_completion_message(
    operation: str,
    total: int,
    dry_run: bool,
    next_step: Optional[str] = None,
) -> None:
    """Prints a consistent completion message for fix commands."""
    console.print(f"\n--- {operation} Complete ---")
    if total == 0 and not dry_run:
        console.print("[bold green]✅ No changes were needed.[/bold green]")
        return
    if dry_run:
        console.print(f"💧 DRY RUN: Found {total} item(s) to fix.")
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(f"✅ APPLIED: Successfully updated {total} item(s).")
        if next_step:
            console.print(f"\n[bold]NEXT STEP:[/bold] {next_step}")


@fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)
# ID: b4f50422-a599-4734-87b6-598fabe4474d
def format_code_wrapper() -> None:
    """Wrapper that calls the dedicated code style service directly."""
    format_code()


@fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)
# ID: 4869877d-a484-425d-88ff-8a63b44ca6ef
def fix_headers_cmd(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes autonomously."
    ),
) -> None:
    """User-friendly wrapper for the header fixing logic, now using the A1 loop."""
    ctx = _ensure_context()
    goal = "Fix all Python file headers in the `src` directory to be constitutionally compliant."
    if write:
        console.print(
            "[bold cyan]🚀 Initiating A1 self-healing for file headers...[/bold cyan]"
        )
        asyncio.run(propose_and_apply_autonomously(context=ctx, goal=goal))
    else:
        console.print(
            "[bold yellow]-- DRY RUN: Generating autonomous plan for fixing headers... --[/bold yellow]"
        )
        # --- START MODIFICATION ---
        asyncio.run(micro_propose(context=ctx, goal=goal))
        # --- END MODIFICATION ---


@fix_app.command(
    "docstrings", help="Adds missing docstrings using the A1 autonomy loop."
)
# ID: 75479ad2-99ab-4f7c-ad07-0c502f66a96e
def fix_docstrings_command(
    write: bool = typer.Option(
        False, "--write", help="Propose and apply the fix autonomously."
    ),
) -> None:
    """Uses the A1 micro-proposal loop to find and add missing docstrings."""
    ctx = _ensure_context()
    goal = "Add missing docstrings to all Python functions and methods in the `src` directory."
    if write:
        asyncio.run(propose_and_apply_autonomously(context=ctx, goal=goal))
    else:
        console.print(
            "[bold yellow]-- DRY RUN: Generating autonomous plan without applying it. --[/bold yellow]"
        )
        # --- START MODIFICATION ---
        asyncio.run(micro_propose(context=ctx, goal=goal))
        # --- END MODIFICATION ---


fix_app.command("line-lengths", help="Refactors files with long lines.")(
    fix_line_lengths
)
fix_app.command("clarity", help="Refactors a file for clarity.")(fix_clarity)


@fix_app.command(
    "complexity", help="Refactors complex code for better separation of concerns."
)
# ID: 2e61896f-cfa3-42fd-95ac-e8e1a7d04111
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
) -> None:
    """Identifies and refactors complexity outliers to improve separation of concerns."""
    complexity_outliers(file_path=file_path, dry_run=not write)


@fix_app.command(
    "ids", help="Assigns a stable '# ID: <uuid>' to all untagged public symbols."
)
# ID: acc209a3-b54c-474d-9ac9-2cc3d04fb24a
def assign_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    """CLI wrapper for the symbol ID tagging service."""
    total_assigned = assign_missing_ids(dry_run=not write)
    _print_completion_message(
        operation="ID Assignment",
        total=total_assigned,
        dry_run=not write,
        next_step="Run 'poetry run core-admin manage database sync-knowledge --write' to update the database.",
    )


@fix_app.command(
    "purge-legacy-tags", help="Removes obsolete '# CAPABILITY:' tags from source code."
)
# ID: c1a30bf9-4a8c-48ac-9fe4-6621dec472ab
def purge_legacy_tags_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    """CLI wrapper for the legacy tag purging service."""
    total_removed = purge_legacy_tags(dry_run=not write)
    _print_completion_message(
        operation="Purge",
        total=total_removed,
        dry_run=not write,
        next_step="Run 'poetry run core-admin manage database sync-knowledge --write' to update the database.",
    )


@fix_app.command(
    "policy-ids", help="Adds a unique `policy_id` UUID to any policy file missing one."
)
# ID: a4a70ed7-2bcd-42c0-9edc-40c6efa796cb
def fix_policy_ids_command(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
) -> None:
    """CLI wrapper for the policy ID migration service."""
    total_updated = add_missing_policy_ids(dry_run=not write)
    _print_completion_message(
        operation="Policy ID Migration",
        total=total_updated,
        dry_run=not write,
        next_step="Run 'poetry run core-admin check audit' to verify constitutional compliance.",
    )


@fix_app.command(
    "tags",
    help="Use an AI agent to suggest and apply capability tags to untagged symbols.",
)
# ID: 3159ad83-bea2-4a10-9d3a-b4598f4f3d1c
def fix_tags_command(
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
) -> None:
    """Wrapper for the CapabilityTaggerAgent that writes to the database."""
    ctx = _ensure_context()
    tag_unassigned_capabilities(
        cognitive_service=ctx.cognitive_service,
        knowledge_service=ctx.knowledge_service,
        file_path=file_path,
        write=write,
    )


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
# ID: fc47ab7d-c9bf-4476-a703-4099c50e3946
def sync_db_registry_command() -> None:
    """CLI wrapper for the command sync service."""
    from cli.admin_cli import app as main_app

    asyncio.run(sync_commands_to_db(main_app))


@fix_app.command(
    "duplicate-ids", help="Finds and fixes duplicate '# ID:' tags in the codebase."
)
# ID: 6d709af4-5ab4-45bc-9360-f05b50d930c9
def fix_duplicate_ids_command(
    write: bool = typer.Option(False, "--write", help="Apply fixes to source files."),
) -> None:
    """CLI wrapper for the duplicate ID resolution service."""
    asyncio.run(resolve_duplicate_ids(dry_run=not write))


fix_app.command(
    "orphaned-vectors",
    help="Finds and deletes vectors in Qdrant that no longer exist in the main DB.",
)(prune_orphaned_vectors)

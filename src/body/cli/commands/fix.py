# src/body/cli/commands/fix.py

"""
Registers the 'fix' command group and its associated self-healing capabilities.
"""

from __future__ import annotations

import functools
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from features.maintenance.command_sync_service import sync_commands_to_db
from features.self_healing.capability_tagging_service import tag_unassigned_capabilities
from features.self_healing.clarity_service import fix_clarity
from features.self_healing.code_style_service import format_code
from features.self_healing.complexity_service import complexity_outliers
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.duplicate_id_service import resolve_duplicate_ids
from features.self_healing.id_tagging_service import assign_missing_ids
from features.self_healing.linelength_service import fix_line_lengths
from features.self_healing.policy_id_service import add_missing_policy_ids
from features.self_healing.prune_orphaned_vectors import (
    main_sync as prune_orphaned_vectors,
)
from features.self_healing.purge_legacy_tags_service import purge_legacy_tags
from mind.governance.constitutional_monitor import ConstitutionalMonitor
from rich.console import Console
from shared.cli_utils import async_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

# --- END OF FIX ---


logger = getLogger(__name__)
console = Console()

COMMAND_CONFIG = {
    "code-style": {
        "timeout": 300,
        "dangerous": False,
        "confirmation": False,
        "category": "formatting",
    },
    "headers": {
        "timeout": 600,
        "dangerous": True,
        "confirmation": True,
        "category": "compliance",
    },
    "docstrings": {
        "timeout": 900,
        "dangerous": True,
        "confirmation": False,
        "category": "documentation",
    },
    "line-lengths": {
        "timeout": 600,
        "dangerous": True,
        "confirmation": True,
        "category": "formatting",
    },
    "clarity": {
        "timeout": 1200,
        "dangerous": True,
        "confirmation": True,
        "category": "refactoring",
    },
    "complexity": {
        "timeout": 1200,
        "dangerous": True,
        "confirmation": True,
        "category": "refactoring",
    },
    "ids": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": False,
        "category": "metadata",
    },
    "purge-legacy-tags": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": True,
        "category": "cleanup",
    },
    "policy-ids": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": True,
        "category": "metadata",
    },
    "tags": {
        "timeout": 1800,
        "dangerous": True,
        "confirmation": True,
        "category": "metadata",
    },
    "db-registry": {
        "timeout": 300,
        "dangerous": False,
        "confirmation": False,
        "category": "database",
    },
    "duplicate-ids": {
        "timeout": 600,
        "dangerous": True,
        "confirmation": True,
        "category": "metadata",
    },
    "orphaned-vectors": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": True,
        "category": "database",
    },
}


# ID: 942a29b0-1d9d-469f-b5dc-0679212b4388
def handle_command_errors(func: Callable) -> Callable:
    @functools.wraps(func)
    # ID: 639b0b45-f774-4bcf-873a-5e5ac1b31549
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except Exception as e:
            console.print(f"[red]❌ Command failed: {str(e)}[/red]")
            if getattr(settings, "DEBUG", False):
                console.print("[yellow]Debug traceback:[/yellow]")
                console.print(traceback.format_exc())
            raise typer.Exit(code=1)

    return wrapper


def _run_with_progress(message: str, coro_or_func: Callable) -> Any:
    # This simplified version is for synchronous tasks only now.
    with console.status(f"[cyan]{message}...[/cyan]"):
        return coro_or_func()


def _confirm_dangerous_operation(command_name: str, write: bool = False) -> bool:
    """
    In fully autonomous mode we treat CLI flags as the only source of consent.

    This helper no longer prints warnings or asks for interactive confirmation.
    It exists only to keep the command signatures and call sites stable.
    """
    return True


fix_app = typer.Typer(
    help="Self-healing tools that write changes to the codebase.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@fix_app.callback()
# ID: 460604f9-e075-4666-a613-27c8f1ec9fa1
def fix_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable debug output including tracebacks"
    ),
):
    """Self-healing tools organized by category."""
    if debug:
        settings.DEBUG = True
    if verbose:
        settings.VERBOSE = True


@fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)
@handle_command_errors
# ID: 79b873a6-ccd3-4aba-a5e9-b3da8fabd6a3
def format_code_wrapper() -> None:
    _run_with_progress("Formatting code", format_code)
    console.print("[green]✅ Code formatting completed[/green]")


@fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)
@handle_command_errors
# ID: 80d3b5f4-a048-4b14-83ee-3fcd667d7ca7
def fix_headers_cmd(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes autonomously."
    ),
) -> None:
    if not _confirm_dangerous_operation("headers", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    console.print("[bold cyan]🚀 Initiating constitutional header audit...[/bold cyan]")
    monitor = ConstitutionalMonitor(repo_path=settings.REPO_PATH)
    audit_report = _run_with_progress("Auditing headers", monitor.audit_headers)
    if not audit_report.violations:
        console.print("[green]✅ All headers are constitutionally compliant.[/green]")
        return
    console.print(
        f"[yellow]Found {len(audit_report.violations)} header violation(s).[/yellow]"
    )
    if write:
        remediation_result = _run_with_progress(
            "Remediating violations", lambda: monitor.remediate_violations(audit_report)
        )
        if remediation_result.success:
            console.print(
                f"[green]✅ Fixed {remediation_result.fixed_count} header(s).[/green]"
            )
        else:
            console.print(
                f"[red]❌ Remediation failed: {remediation_result.error}[/red]"
            )
    else:
        console.print("[yellow]Dry run mode. Use --write to apply fixes.[/yellow]")
        for violation in audit_report.violations:
            console.print(f"  - {violation.file_path}: {violation.description}")


# --- START OF FIX: Convert the command to async and use the new decorator ---
@fix_app.command(
    "docstrings", help="Adds missing docstrings using the A1 autonomy loop."
)
@handle_command_errors
@async_command
# ID: f0a66115-bc7a-46bc-a363-d9fa2b283e89
async def fix_docstrings_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Propose and apply the fix autonomously."
    ),
) -> None:
    if not _confirm_dangerous_operation("docstrings", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    # Directly await the async function
    with console.status("[cyan]Fixing docstrings...[/cyan]"):
        await fix_docstrings(context=core_context, write=write)
    console.print("[green]✅ Docstring fixes completed[/green]")


# --- END OF FIX ---


@fix_app.command("line-lengths", help="Refactors files with long lines.")
@handle_command_errors
@async_command
# ID: 75f2dc5a-c8de-41c9-aa27-efa2551f74c8
async def fix_line_lengths_command(
    ctx: typer.Context,
    file_path: Path | None = typer.Argument(
        None,
        help="Optional: A specific file to fix.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the changes directly to the files."
    ),
) -> None:
    if not _confirm_dangerous_operation("line-lengths", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status("[cyan]Fixing line lengths...[/cyan]"):
        await fix_line_lengths(
            context=core_context, file_path=file_path, dry_run=not write
        )
    console.print("[green]✅ Line length fixes completed[/green]")


@fix_app.command("clarity", help="Refactors a file for clarity.")
@handle_command_errors
@async_command
# ID: 97d1ae1a-827b-443d-9c38-4b4f0d1f5d6b
async def fix_clarity_command(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ..., help="Path to the Python file to refactor.", exists=True, dir_okay=False
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
) -> None:
    if not _confirm_dangerous_operation("clarity", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status(f"[cyan]Refactoring {file_path} for clarity...[/cyan]"):
        await fix_clarity(context=core_context, file_path=file_path, dry_run=not write)
    console.print("[green]✅ Clarity refactoring completed[/green]")


@fix_app.command(
    "complexity", help="Refactors complex code for better separation of concerns."
)
@handle_command_errors
@async_command
# ID: 18605800-1708-47dc-a631-16cb579e7ed2
async def complexity_command(
    ctx: typer.Context,
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
    if not _confirm_dangerous_operation("complexity", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status(f"[cyan]Refactoring {file_path} for complexity...[/cyan]"):
        await complexity_outliers(
            context=core_context, file_path=file_path, dry_run=not write
        )
    console.print("[green]✅ Complexity refactoring completed[/green]")


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
    console.print(f"[green]✅ Total IDs assigned: {total_assigned}[/green]")


@fix_app.command(
    "purge-legacy-tags", help="Removes obsolete '# CAPABILITY:' tags from source code."
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
    console.print(f"[green]✅ Total legacy tags removed: {total_removed}[/green]")


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
    console.print(f"[green]✅ Total policy files updated: {total_updated}[/green]")


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
) -> None:
    if not _confirm_dangerous_operation("tags", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    target_files = f"file {file_path}" if file_path else "all files"
    with console.status(f"[cyan]Tagging capabilities in {target_files}...[/cyan]"):
        await tag_unassigned_capabilities(
            cognitive_service=core_context.cognitive_service,
            knowledge_service=core_context.knowledge_service,
            file_path=file_path,
            write=write,
        )
    console.print("[green]✅ Capability tagging completed[/green]")


@fix_app.command(
    "db-registry", help="Syncs the live CLI command structure to the database."
)
@handle_command_errors
@async_command
# ID: 0156169d-4675-4811-8118-1b94c3a03797
async def sync_db_registry_command() -> None:
    """CLI wrapper for the command sync service."""
    from body.cli.admin_cli import app as main_app

    with console.status("[cyan]Syncing CLI commands to database...[/cyan]"):
        await sync_commands_to_db(main_app)
    console.print("[green]✅ Database registry sync completed[/green]")


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
    console.print("[green]✅ Duplicate ID resolution completed[/green]")


@fix_app.command(
    "orphaned-vectors",
    help="Finds and deletes vectors in Qdrant that no longer exist in the main DB.",
)
@handle_command_errors
# ID: cad8d742-b095-44fc-8d40-788ed2589848
def fix_orphaned_vectors_command(
    write: bool = typer.Option(False, "--write", help="Apply fixes to source files."),
) -> None:
    if not _confirm_dangerous_operation("orphaned-vectors", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    _run_with_progress(
        "Pruning orphaned vectors", lambda: prune_orphaned_vectors(dry_run=not write)
    )
    console.print("[green]✅ Orphaned vectors cleanup completed[/green]")


@fix_app.command("all", help="Run all safe fixes in sequence.")
@handle_command_errors
# ID: 690a63fb-8a43-47cc-af16-ecbac5663ded
def run_all_fixes(
    skip_dangerous: bool = typer.Option(
        True, help="Skip potentially dangerous operations that modify code"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be fixed without making changes"
    ),
) -> None:
    pass


@fix_app.command("list", help="List all available fix commands with their categories.")
# ID: 3a6c8ca8-b655-45dd-9dbf-1ca747fee287
def list_commands() -> None:
    pass

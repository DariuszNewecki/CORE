# src/body/cli/commands/fix/__init__.py
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
from features.self_healing.linelength_service import fix_line_lengths
from rich.console import Console
from shared.cli_utils import async_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

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
    "dangling-vector-links": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": True,
        "category": "database",
    },
    "ir-triage": {
        "timeout": 60,
        "dangerous": False,
        "confirmation": False,
        "category": "incident-response",
    },
    "ir-log": {
        "timeout": 60,
        "dangerous": False,
        "confirmation": False,
        "category": "incident-response",
    },
    "atomic-actions": {
        "timeout": 300,
        "dangerous": True,
        "confirmation": False,
        "category": "compliance",
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


# Late imports so submodules can register additional commands on fix_app
from . import (
    all_commands,  # noqa: F401
    atomic_actions,  # noqa: F401  -- NEW: Register atomic-actions command
    clarity,  # noqa: F401
    code_style,  # noqa: F401
    db_tools,  # noqa: F401
    docstrings,  # noqa: F401
    fix_ir,  # noqa: F401
    handler_discovery,  # noqa: F401
    list_commands,  # noqa: F401
    metadata,  # noqa: F401
)

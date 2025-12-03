# src/body/cli/commands/fix/atomic_actions_cmd.py

"""
Fix atomic actions pattern violations command registration.

This module registers the atomic-actions fix command with the fix command group.
"""

from __future__ import annotations

from pathlib import Path

import typer
from shared.logger import getLogger

from . import console, fix_app, handle_command_errors

logger = getLogger(__name__)


@fix_app.command(
    "atomic-actions",
    help="Fix atomic actions pattern violations (missing decorators, return types, metadata).",
)
@handle_command_errors
# ID: 8c7e9f4a-6d5b-3e2a-9c8f-7b6d9e4a8c7f
def fix_atomic_actions_command(
    file: str = typer.Option(
        None,
        "--file",
        help="Fix specific file only",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes (default: dry-run preview)",
    ),
) -> None:
    """
    Automatically fix atomic actions pattern violations.

    Fixes:
    - Missing @atomic_action decorators
    - Missing -> ActionResult return type annotations
    - Missing decorator metadata (action_id, intent, impact, policies)

    Pattern: action_pattern
    Default: dry-run (shows what would be fixed)
    Use --write to apply changes
    """
    try:
        # Import the actual implementation from the generated file
        from .atomic_actions import fix_atomic_actions_internal

        root_path = Path(file) if file else Path.cwd()

        console.print("🔍 Scanning for atomic actions violations...")

        result = fix_atomic_actions_internal(
            root_path=root_path,
            write=write,
        )

        # CommandResult uses 'ok' not 'success'
        if result.ok:
            if write:
                console.print(f"[green]✅ {result.data}[/green]")
                console.print(
                    f"[green]Fixed {result.data['violations_fixed']} violations in {result.data['files_modified']} files[/green]"
                )
            else:
                console.print(
                    f"[yellow]📋 Preview: Would fix {result.data['violations_fixed']} violations in {result.data['files_modified']} files[/yellow]"
                )
                console.print("[cyan]Run with --write to apply fixes[/cyan]")
        else:
            console.print("[red]❌ Failed to fix atomic actions[/red]")
            raise typer.Exit(code=1)

    except ImportError as e:
        logger.error(f"Failed to import atomic_actions module: {e}")
        console.print("[red]❌ atomic_actions module not found[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Failed to fix atomic actions: {e}")
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(code=1)

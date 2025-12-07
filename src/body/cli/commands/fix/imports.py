# src/body/cli/commands/fix/imports.py

"""
Import organization commands for the 'fix' CLI group.

Provides:
- fix imports (Sort and group imports according to PEP 8)
"""

from __future__ import annotations

import typer
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.utils.subprocess_utils import run_poetry_command

from . import (
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "imports",
    help="Sort and group imports according to PEP 8 (stdlib → third-party → local).",
)
@handle_command_errors
@core_command(dangerous=False)
# ID: a8b9c0d1-e2f3-4a5b-6c7d-8e9f0a1b2c3d
async def fix_imports_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write/--dry-run",
        help="Apply import sorting (default: dry-run)",
    ),
) -> None:
    """
    Sort and group Python imports according to constitutional style policy.

    Groups imports in the correct order:
    1. Standard library
    2. Third-party packages
    3. Local imports

    Uses ruff's import sorting (I) rules.
    """
    target_path = "src/"

    console.print("[bold cyan]Sorting imports...[/bold cyan]")
    console.print(f"Target: {target_path}")
    console.print(f"Mode: {'WRITE' if write else 'DRY RUN'}")

    try:
        # Build ruff command
        cmd = ["ruff", "check", target_path, "--select", "I"]

        if write:
            cmd.append("--fix")

        cmd.append("--exit-zero")  # Don't fail on violations

        # Execute via sanctioned subprocess utility
        run_poetry_command(
            f"Sorting imports in {target_path}",
            cmd,
        )

        console.print("[green]✅ Import sorting completed[/green]")

    except Exception as e:
        console.print(f"[red]❌ Import sorting failed: {e}[/red]")
        raise typer.Exit(1)


# Atomic action wrapper for internal use
@atomic_action(
    action_id="fix.imports",
    intent="Sort and group Python imports according to PEP 8 conventions",
    impact=ActionImpact.WRITE_METADATA,
    policies=["import_organization"],
    category="fixers",
)
async def fix_imports_internal(write: bool = False) -> ActionResult:
    """
    Internal atomic action for import sorting.

    Used by dev sync workflow and other orchestrators.
    """
    import time

    target_path = "src/"
    start = time.time()

    try:
        # Build ruff command
        cmd = ["ruff", "check", target_path, "--select", "I"]

        if write:
            cmd.append("--fix")

        cmd.append("--exit-zero")

        # Execute
        run_poetry_command(
            f"Sorting imports in {target_path}",
            cmd,
        )

        return ActionResult(
            action_id="fix.imports",
            ok=True,
            data={"status": "completed", "target": target_path, "write": write},
            duration_sec=time.time() - start,
        )

    except Exception as e:
        return ActionResult(
            action_id="fix.imports",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )

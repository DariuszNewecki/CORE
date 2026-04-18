# src/cli/commands/fix/imports.py
"""
Import organization commands for the 'fix' CLI group.

Provides:
- fix imports (Sort and group imports according to PEP 8)

CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Enforces import organization standards via standard tooling.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer

from cli.utils import core_command
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.utils.subprocess_utils import run_poetry_command

from . import fix_app


@fix_app.command(
    "imports",
    help="Sort and group imports according to PEP 8 (stdlib → third-party → local).",
)
@core_command(dangerous=False)
# ID: da8cd296-1100-48b8-b87a-1edeafa5db15
async def fix_imports_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write/--dry-run", help="Apply import sorting (default: dry-run)"
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
    logger.info("[bold cyan]Sorting imports...[/bold cyan]")
    logger.info("Target: %s", target_path)
    logger.info("Mode: %s", "WRITE" if write else "DRY RUN")
    try:
        cmd = ["ruff", "check", target_path, "--select", "I"]
        if write:
            cmd.append("--fix")
        cmd.append("--exit-zero")
        run_poetry_command(f"Sorting imports in {target_path}", cmd)
        logger.info("[green]✅ Import sorting completed[/green]")
    except Exception as e:
        logger.info("[red]❌ Import sorting failed: %s[/red]", e)
        raise typer.Exit(1)


@atomic_action(
    action_id="fix.imports",
    intent="Sort and group Python imports according to PEP 8 conventions",
    impact=ActionImpact.WRITE_METADATA,
    policies=["import_organization"],
    category="fixers",
)
# ID: 0fc1ca3d-ca25-4c3d-ba07-b25abe44c95a
async def fix_imports_internal(write: bool = False) -> ActionResult:
    """
    Internal atomic action for import sorting.

    Used by dev sync workflow and other orchestrators.
    """
    import time

    target_path = "src/"
    start = time.time()
    try:
        cmd = ["ruff", "check", target_path, "--select", "I"]
        if write:
            cmd.append("--fix")
        cmd.append("--exit-zero")
        run_poetry_command(f"Sorting imports in {target_path}", cmd)
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

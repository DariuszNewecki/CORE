# src/body/cli/commands/fix/code_style.py
"""
Code style and formatting commands for the 'fix' CLI group.

Provides:
- fix code-style (Black + Ruff formatting)
- fix headers (file header compliance)
"""

from __future__ import annotations

import typer

from features.self_healing.code_style_service import format_code
from features.self_healing.header_service import _run_header_fix_cycle
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext

from . import (
    _run_with_progress,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)
@handle_command_errors
@core_command(dangerous=False)
# ID: 227222a1-811d-4fd8-bd32-65329f8414ca
def format_code_cmd(ctx: typer.Context) -> None:
    """
    CLI entry point for `fix code-style`.
    Delegates to Black & Ruff via subprocesses.
    """
    _run_with_progress("Formatting code", format_code)
    console.print("[green]✅ Code formatting completed[/green]")


@atomic_action(
    action_id="fix.headers",
    intent="Ensure all Python files have constitutionally compliant headers",
    impact=ActionImpact.WRITE_METADATA,
    policies=["file_headers"],
    category="fixers",
)
# ID: edb6d962-f821-475d-8885-ca8518569758
async def fix_headers_internal(
    context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Core logic for fix headers command. Now uses governed ActionExecutor.
    """
    import time

    start_time = time.time()

    try:
        # Get all Python files in src/
        src_dir = settings.REPO_PATH / "src"
        all_py_files = [
            str(p.relative_to(settings.REPO_PATH)) for p in src_dir.rglob("*.py")
        ]

        # FIXED: _run_header_fix_cycle is now async and requires context
        await _run_header_fix_cycle(
            context, dry_run=not write, all_py_files=all_py_files
        )

        return ActionResult(
            action_id="fix.headers",
            ok=True,
            data={
                "files_scanned": len(all_py_files),
                "dry_run": not write,
                "mode": "write" if write else "dry-run",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA if write else ActionImpact.READ_ONLY,
        )

    except Exception as e:
        return ActionResult(
            action_id="fix.headers",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during header fix: {e}"],
        )


@fix_app.command(
    "headers", help="Ensures all files have constitutionally compliant headers."
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: 967c7322-5732-466f-a639-cacbaae425ba
async def fix_headers_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix headers command.
    """
    # FIXED: Pass CoreContext (ctx.obj)
    with console.status("[cyan]Checking file headers...[/cyan]"):
        return await fix_headers_internal(ctx.obj, write=write)

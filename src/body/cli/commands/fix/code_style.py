# src/body/cli/commands/fix/code_style.py
"""
Code style and formatting commands for the 'fix' CLI group.

Provides:
- fix headers (file header compliance)

CONSTITUTIONAL ALIGNMENT:
- Logic decoupled from CLI helpers to prevent circular imports.
- Mutation logic remains in 'internal' functions for Atomic Action use.
"""

from __future__ import annotations

import time

import typer

from features.self_healing.header_service import _run_header_fix_cycle
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.context import CoreContext

# We only import the App and Console from the local hub
from . import console, fix_app


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
    start_time = time.time()

    # CONSTITUTIONAL FIX: Use context.git_service.repo_path instead of settings.REPO_PATH
    repo_root = context.git_service.repo_path

    try:
        # Get all Python files in src/
        src_dir = repo_root / "src"
        all_py_files = [str(p.relative_to(repo_root)) for p in src_dir.rglob("*.py")]

        # _run_header_fix_cycle is async and requires context
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
@core_command(dangerous=True, confirmation=True)
# ID: 967c7322-5732-466f-a639-cacbaae425ba
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for fix_headers_cmd",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 3fcdcae8-f417-41e3-bc81-1b09a39e2887
async def fix_headers_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix headers command.
    """
    with console.status("[cyan]Checking file headers...[/cyan]"):
        return await fix_headers_internal(ctx.obj, write=write)

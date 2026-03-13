# src/cli/commands/fix/code_style.py
"""
Code style and formatting commands for the 'fix' CLI group.

Provides:
- fix headers (file header compliance)

CONSTITUTIONAL ALIGNMENT:
- Logic decoupled from CLI helpers to prevent circular imports.
- Mutation logic remains in 'internal' functions for Atomic Action use.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import time

import typer

from body.self_healing.header_service import _run_header_fix_cycle
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.context import CoreContext

from . import fix_app


@atomic_action(
    action_id="fix.headers",
    intent="Ensure all Python files have constitutionally compliant headers",
    impact=ActionImpact.WRITE_METADATA,
    policies=["file_headers"],
    category="fixers",
)
# ID: 936e32e6-18a3-4b7c-a0f2-06cc8ca654f7
async def fix_headers_internal(
    context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Core logic for fix headers command. Now uses governed ActionExecutor.
    """
    start_time = time.time()
    repo_root = context.git_service.repo_path
    try:
        src_dir = repo_root / "src"
        all_py_files = [
            p.relative_to(repo_root).as_posix() for p in src_dir.rglob("*.py")
        ]
        summary = await _run_header_fix_cycle(
            context, dry_run=not write, all_py_files=all_py_files
        )
        return ActionResult(
            action_id="fix.headers",
            ok=True,
            data={
                "total_files_scanned": summary["total_files_scanned"],
                "files_changed": summary["files_changed"],
                "files_unchanged": summary["files_unchanged"],
                "files_created": summary["files_created"],
                "changed_file_paths": summary["changed_file_paths"],
                "files_scanned": summary["total_files_scanned"],
                "violations_found": summary["files_changed"],
                "fixed_count": summary["files_changed"] if write else 0,
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
            data={"error": str(e), "error_type": type(e).__name__},
            duration_sec=time.time() - start_time,
            logs=[f"Exception during header fix: {e}"],
        )


@fix_app.command(
    "headers", help="Ensures all files have constitutionally compliant headers."
)
@core_command(dangerous=True, confirmation=True)
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for fix_headers_cmd",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 0077efbb-9090-42bb-a602-2ff3b7853875
async def fix_headers_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix headers command.
    """
    with logger.info("[cyan]Checking file headers...[/cyan]"):
        return await fix_headers_internal(ctx.obj, write=write)

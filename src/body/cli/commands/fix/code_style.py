# src/body/cli/commands/fix/code_style.py
"""
Code style related self-healing commands for the 'fix' CLI group.
"""

from __future__ import annotations

import time

import typer
from features.self_healing.code_style_service import format_code
from mind.governance.constitutional_monitor import ConstitutionalMonitor
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command
from shared.config import settings

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
    # Note: _run_with_progress is kept here as it wraps subprocess calls specifically
    _run_with_progress("Formatting code", format_code)
    console.print("[green]✅ Code formatting completed[/green]")


# ID: fix_headers_internal_v1
@atomic_action(
    action_id="fix.headers",
    intent="Ensure all Python files have constitutionally compliant headers",
    impact=ActionImpact.WRITE_METADATA,
    policies=["file_headers"],
    category="fixers",
)
# ID: edb6d962-f821-475d-8885-ca8518569758
async def fix_headers_internal(write: bool = False) -> ActionResult:
    """
    Core logic for fix headers command.
    Audits and optionally remediates file headers.
    """
    start_time = time.time()

    try:
        # Step 1: Audit
        monitor = ConstitutionalMonitor(repo_path=settings.REPO_PATH)
        audit_report = monitor.audit_headers()

        # Base data (always present)
        result_data = {
            "violations_found": len(audit_report.violations),
            "files_scanned": audit_report.total_files_scanned,
            "compliant_files": audit_report.compliant_files,
            "dry_run": not write,
        }

        # Case A: No violations found
        if not audit_report.violations:
            return ActionResult(
                action_id="fix.headers",
                ok=True,
                data=result_data,
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_METADATA,
            )

        # Case B: Write mode (Fix violations)
        if write:
            remediation_result = monitor.remediate_violations(audit_report)
            result_data.update(
                {
                    "fixed_count": remediation_result.fixed_count,
                    "failed_count": remediation_result.failed_count,
                }
            )

            return ActionResult(
                action_id="fix.headers",
                ok=remediation_result.success,
                data=result_data,
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_METADATA,
                suggestions=(
                    ["Run check audit to verify compliance"]
                    if remediation_result.success
                    else []
                ),
            )

        # Case C: Dry-run mode (Report violations)
        return ActionResult(
            action_id="fix.headers",
            ok=True,  # Operation "succeeded" in reporting status
            data=result_data,
            duration_sec=time.time() - start_time,
            suggestions=["Run with --write to fix violations"],
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
            logs=[f"Exception during header audit/remediation: {e}"],
        )


@fix_app.command(
    "headers", help="Ensures all Python files have constitutionally compliant headers."
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
    # The framework handles:
    # 1. Safety checks (confirmation prompt)
    # 2. Async loop management
    # 3. Error handling
    # 4. Output formatting (via ActionResult)

    with console.status("[cyan]Checking file headers...[/cyan]"):
        return await fix_headers_internal(write=write)

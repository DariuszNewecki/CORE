# src/body/cli/commands/fix/code_style.py
"""
Code style related self-healing commands for the 'fix' CLI group.

Provides:
- fix code-style
- fix headers (MIGRATED to ActionResult pattern with @atomic_action)
"""

from __future__ import annotations

import time

import typer
from features.self_healing.code_style_service import format_code
from mind.governance.constitutional_monitor import ConstitutionalMonitor
from shared.action_types import (
    ActionImpact,
    ActionResult,
)

# CHANGED: Import from action_types
from shared.atomic_action import atomic_action  # NEW: Import decorator
from shared.cli_utils import async_command
from shared.config import settings

from . import (
    _confirm_dangerous_operation,
    _run_with_progress,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "code-style", help="Auto-format all code to be constitutionally compliant."
)
@handle_command_errors
# ID: 79b873a6-ccd3-4aba-a5e9-b3da8fabd6a3
def format_code_cmd() -> None:
    """
    CLI entry point for `fix code-style`.

    Delegates to the code style self-healing service to run Black & Ruff
    in a constitutionally aware way.
    """
    _run_with_progress("Formatting code", format_code)
    console.print("[green]✅ Code formatting completed[/green]")


# ============================================================================
# NEW: Internal function with ActionResult and @atomic_action
# ============================================================================


# ID: fix_headers_internal_v1
@atomic_action(
    action_id="fix.headers",
    intent="Ensure all Python files have constitutionally compliant headers",
    impact=ActionImpact.WRITE_METADATA,
    policies=["file_headers"],
    category="fixers",
)
# ID: 598ba917-d84a-4bce-9bbc-27d62733aeed
async def fix_headers_internal(write: bool = False) -> ActionResult:
    """
    Core logic for fix headers command.

    Audits all Python files for constitutional header compliance and
    optionally remediates violations. Headers must include:
    - File path comment
    - Module docstring
    - Required imports

    This ensures:
    - Consistent file structure across codebase
    - Constitutional compliance for AI code generation
    - Proper documentation for knowledge graph

    Args:
        write: If True, fix violations. If False, audit only (dry-run).

    Returns:
        ActionResult with:
        - ok: True if no violations or all fixed successfully
        - data: {
            "violations_found": int,
            "files_scanned": int,
            "compliant_files": int,
            "fixed_count": int (only if write=True),
            "failed_count": int (only if write=True),
            "dry_run": bool,
          }
        - duration_sec: Execution time
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

        # If no violations, we're done
        if not audit_report.violations:
            return ActionResult(
                action_id="fix.headers",
                ok=True,
                data=result_data,
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_METADATA,
            )

        # Step 2: Remediate (if write mode)
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

        # Dry-run: violations found but not fixed
        return ActionResult(
            action_id="fix.headers",
            ok=False,  # Violations exist but not fixed
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
@async_command
# ID: 00b6c8e4-9e5d-4a9a-8c3a-7f6e5d4c3b2a
async def fix_headers_cmd(
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> None:
    """
    CLI wrapper for fix headers command.

    Handles user interaction and presentation while fix_headers_internal()
    contains the core logic. This separation enables:
    - Testing without CLI
    - Workflow orchestration
    - Constitutional governance
    """

    if not _confirm_dangerous_operation("headers", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    # Call internal function
    with console.status("[cyan]Checking file headers...[/cyan]"):
        result = await fix_headers_internal(write=write)

    # Present results
    if result.ok:
        violations = result.data.get("violations_found", 0)
        if violations == 0:
            console.print(
                "[bold green]✅ All headers are constitutionally compliant.[/bold green]"
            )
        else:
            fixed = result.data.get("fixed_count", 0)
            console.print(
                f"[bold green]✅ Fixed {fixed}/{violations} header violations.[/bold green]"
            )
    else:
        violations = result.data.get("violations_found", 0)
        if "error" in result.data:
            error = result.data["error"]
            console.print(f"[bold red]❌ Error: {error}[/bold red]")
        else:
            console.print(
                f"[yellow]⚠ Found {violations} header violations (dry-run mode).[/yellow]"
            )
            console.print("[dim]Run with --write to fix them.[/dim]")

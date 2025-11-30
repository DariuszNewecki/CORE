# src/body/cli/commands/fix/code_style.py
"""
Code style related self-healing commands for the 'fix' CLI group.

Provides:
- fix code-style
- fix headers (MIGRATED to CommandResult pattern)
"""

from __future__ import annotations

import time

import typer
from features.self_healing.code_style_service import format_code
from mind.governance.constitutional_monitor import ConstitutionalMonitor
from shared.cli_types import CommandResult
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
# NEW: Internal function that returns CommandResult
# ============================================================================


# ID: fix_headers_internal_v1
# ID: 92312357-aedb-4381-8b5c-e824877871d9
async def fix_headers_internal(write: bool = False) -> CommandResult:
    """
    Core logic for fix headers command.

    Returns CommandResult with audit and remediation data.

    Args:
        write: Whether to apply fixes (False = dry-run audit only)

    Returns:
        CommandResult with:
            - name: "fix.headers"
            - ok: True if no violations or all fixed successfully
            - data: {
                "violations_found": int,
                "files_scanned": int,
                "compliant_files": int,
                "fixed_count": int (only if write=True),
                "failed_count": int (only if write=True),
                "dry_run": bool,
              }
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
            return CommandResult(
                name="fix.headers",
                ok=True,
                data=result_data,
                duration_sec=time.time() - start_time,
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

            return CommandResult(
                name="fix.headers",
                ok=remediation_result.success,
                data=result_data,
                duration_sec=time.time() - start_time,
            )

        # Dry-run: violations found but not fixed
        return CommandResult(
            name="fix.headers",
            ok=False,  # Violations exist but not fixed
            data=result_data,
            duration_sec=time.time() - start_time,
        )

    except Exception as e:
        return CommandResult(
            name="fix.headers",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during header processing: {e}"],
        )


# ============================================================================
# CLI Command (refactored to use fix_headers_internal)
# ============================================================================


@fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)
@handle_command_errors
@async_command
# ID: 80d3b5f4-a048-4b14-83ee-3fcd667d7ca7
async def fix_headers_cmd(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes autonomously."
    ),
) -> None:
    """CLI wrapper - presentation only."""

    if not _confirm_dangerous_operation("headers", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return

    console.print("[bold cyan]🚀 Initiating constitutional header audit...[/bold cyan]")

    # Call internal function
    with console.status("[cyan]Auditing headers...[/cyan]"):
        result = await fix_headers_internal(write=write)

    # Present results
    if not result.ok and result.data.get("error"):
        # Fatal error occurred
        error = result.data["error"]
        console.print(f"[red]❌ Failed: {error}[/red]")
        raise typer.Exit(1)

    violations = result.data.get("violations_found", 0)

    if violations == 0:
        console.print("[green]✅ All headers are constitutionally compliant.[/green]")
        return

    console.print(f"[yellow]Found {violations} header violation(s).[/yellow]")

    if write:
        fixed = result.data.get("fixed_count", 0)
        failed = result.data.get("failed_count", 0)

        if result.ok:
            console.print(f"[green]✅ Fixed {fixed} header(s).[/green]")
        else:
            console.print(f"[red]❌ Fixed {fixed}, but {failed} failed.[/red]")
            raise typer.Exit(1)
    else:
        console.print("[yellow]Dry run mode. Use --write to apply fixes.[/yellow]")

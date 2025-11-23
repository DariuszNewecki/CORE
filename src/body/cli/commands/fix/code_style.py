# src/body/cli/commands/fix/code_style.py
"""
Code style related self-healing commands for the 'fix' CLI group.

Provides:
- fix code-style
- fix headers
"""

from __future__ import annotations

import typer

from features.self_healing.code_style_service import format_code
from mind.governance.constitutional_monitor import ConstitutionalMonitor
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


@fix_app.command(
    "headers", help="Enforces constitutional header conventions on Python files."
)
@handle_command_errors
# ID: 80d3b5f4-a048-4b14-83ee-3fcd667d7ca7
def fix_headers_cmd(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes autonomously."
    ),
) -> None:
    if not _confirm_dangerous_operation("headers", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    console.print("[bold cyan]🚀 Initiating constitutional header audit...[/bold cyan]")
    monitor = ConstitutionalMonitor(repo_path=settings.REPO_PATH)
    audit_report = _run_with_progress("Auditing headers", monitor.audit_headers)
    if not audit_report.violations:
        console.print("[green]✅ All headers are constitutionally compliant.[/green]")
        return
    console.print(
        f"[yellow]Found {len(audit_report.violations)} header violation(s).[/yellow]"
    )
    if write:
        remediation_result = _run_with_progress(
            "Remediating violations", lambda: monitor.remediate_violations(audit_report)
        )
        if remediation_result.success:
            console.print(
                f"[green]✅ Fixed {remediation_result.fixed_count} header(s).[/green]"
            )
        else:
            console.print(
                f"[red]❌ Remediation failed: {remediation_result.error}[/red]"
            )
    else:
        console.print("[yellow]Dry run mode. Use --write to apply fixes.[/yellow]")
        for violation in audit_report.violations:
            console.print(f"  - {violation.file_path}: {violation.description}")

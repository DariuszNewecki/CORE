# src/cli/logic/audit.py
"""
Implements high-level CI and system health checks, including the main constitutional audit.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from features.governance.constitutional_auditor import ConstitutionalAuditor
from shared.context import CoreContext
from shared.models import AuditSeverity

from .cli_utils import (
    _run_poetry_command,
    find_test_file_for_capability_async,
)

console = Console()

# Global variable to store context, set by the registration layer.
_context: Optional[CoreContext] = None


# ID: 8afdeab9-fc81-4d7c-b05f-dd27f936b3e6
def lint():
    """Checks code formatting and quality using Black and Ruff."""
    _run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    _run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


# ID: f4d514f7-e277-446e-98ff-06e881710a99
def test_system(
    target: str | None = typer.Argument(
        None, help="Optional: A specific test file path or a capability ID."
    )
):
    """Run the pytest suite, optionally targeting a specific test file or capability."""

    async def _async_test_system():
        command = ["pytest"]
        description = "🧪 Running all tests with pytest..."
        if isinstance(target, str):
            target_path = Path(target)
            if target_path.exists() and target_path.is_file():
                command.append(str(target_path))
                description = f"🧪 Running tests for file: {target}"
            else:
                test_file = await find_test_file_for_capability_async(target)
                if test_file:
                    command.append(str(test_file))
                    description = (
                        f"🧪 Running tests for ID '{target}' in {test_file.name}..."
                    )
                else:
                    console.print(
                        f"❌ Could not find a test file for target: '{target}'."
                    )
                    raise typer.Exit(code=1)
        _run_poetry_command(description, command)

    asyncio.run(_async_test_system())


# ID: f7bc6512-03d2-4bf9-b718-6fb9323e38ea
def audit(
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
):
    """Run a full constitutional self-audit and print a summary of findings."""
    if _context is None:
        console.print("[bold red]Error: Context not initialized for audit[/bold red]")
        raise typer.Exit(code=1)

    async def _async_audit():
        auditor = ConstitutionalAuditor(_context.auditor_context)
        passed, all_findings, unassigned_count = await auditor.run_full_audit_async()

        try:
            min_severity = AuditSeverity[severity.upper()]
        except KeyError:
            console.print(
                f"[bold red]Invalid severity level '{severity}'. Must be 'info', 'warning', or 'error'.[/bold red]"
            )
            raise typer.Exit(code=1)

        filtered_findings = [f for f in all_findings if f.severity >= min_severity]

        summary_table = Table.grid(expand=True, padding=(0, 1))
        summary_table.add_column(justify="left")
        summary_table.add_column(justify="right", style="bold")
        errors = [f for f in all_findings if f.severity.is_blocking]
        warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]
        summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
        summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
        summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")

        title = "✅ AUDIT PASSED" if passed else "❌ AUDIT FAILED"
        style = "bold green" if passed else "bold red"
        console.print(Panel(summary_table, title=title, style=style, expand=False))

        if filtered_findings:
            console.print("\n[bold]Audit Findings:[/bold]")
            findings_table = Table()
            findings_table.add_column("Severity", style="bold")
            findings_table.add_column("Check ID")
            findings_table.add_column("Message")
            findings_table.add_column("File:Line")

            for f in sorted(filtered_findings, key=lambda x: x.severity, reverse=True):
                color = {"error": "red", "warning": "yellow", "info": "cyan"}.get(
                    str(f.severity), "white"
                )
                loc = (
                    f"{f.file_path}:{f.line_number}"
                    if f.file_path and f.line_number
                    else f.file_path or ""
                )
                findings_table.add_row(
                    f"[{color}]{str(f.severity).upper()}[/{color}]",
                    f.check_id,
                    f.message,
                    loc,
                )

            console.print(findings_table)

        if not passed:
            raise typer.Exit(1)

    asyncio.run(_async_audit())

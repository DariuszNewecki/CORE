# src/cli/commands/ci.py
"""
Implements high-level CI and system health checks.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from cli.commands.cli_utils import (
    _run_poetry_command,
    find_test_file_for_capability_async,
)
from core.service_registry import service_registry

console = Console()
ci_app = typer.Typer(help="High-level CI and system health checks.")


@ci_app.command(
    "lint",
    help="Check code formatting and quality with Black and Ruff without changing files.",
)
# ID: 3713a069-0edb-4488-996a-55f5d81b21a7
def lint():
    """Checks code formatting and quality using Black and Ruff."""
    _run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    _run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


@ci_app.command("test", help="Run the pytest suite.")
# ID: ee519092-3ea8-4ee8-ad4d-674f739b1d4d
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


@ci_app.command(
    "audit",
    help="Run the full constitutional self-audit and print a summary of findings.",
)
# ID: d2fff57e-241c-4758-a3fb-ae7c07af8937
def audit():
    """Run a full constitutional self-audit and print a summary of findings."""
    auditor = service_registry.get_service("auditor")
    # run_full_audit is now a synchronous wrapper around the async logic
    passed, findings, unassigned_count = auditor.run_full_audit()

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    errors = [f for f in findings if f.severity.is_blocking]
    warnings = [f for f in findings if not f.severity.is_blocking]
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")
    title = "✅ ALL CHECKS PASSED" if passed else "❌ AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if not passed:
        raise typer.Exit(1)


@ci_app.command(
    "report", help="Run a full audit and save the detailed findings to a JSON file."
)
# ID: fae1aafa-0aa5-44c8-b055-97b573ffca67
def audit_report(
    output_path: Path = typer.Option(
        "reports/audit_report.json",
        "--output",
        "-o",
        help="Path to save the JSON report file.",
    )
):
    """Runs a full constitutional audit and saves the detailed findings to a JSON file."""
    console.print(
        "[bold cyan]🚀 Running full audit and generating report...[/bold cyan]"
    )
    auditor = service_registry.get_service("auditor")
    passed, findings, unassigned_count = auditor.run_full_audit()

    report = {
        "passed": passed,
        "summary": {
            "errors": len([f for f in findings if f.severity.is_blocking]),
            "warnings": len([f for f in findings if not f.severity.is_blocking]),
            "unassigned_symbols": unassigned_count,
        },
        "findings": [f.as_dict() for f in findings],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    console.print(f"[bold green]✅ Audit report saved to: {output_path}[/bold green]")
    console.print(JSON(json.dumps(report["summary"])))

# src/body/cli/commands/check/quality_gates.py
# ID: quality-gates-command

"""
Quality Gates Command - Runs all industry-standard quality checks.

Executes the six mandatory quality gates:
1. ruff - Linting
2. mypy - Type checking
3. pytest - Test coverage
4. pip-audit - Security vulnerabilities
5. radon - Complexity analysis
6. vulture - Dead code detection
"""

from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.config import settings


console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: db25d01d-f735-4df1-ac36-f8402e09a722
def quality_gates_cmd(
    ctx: typer.Context,
    fix: bool = typer.Option(False, "--fix", help="Attempt to auto-fix violations"),
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
) -> None:
    """
    Run all quality gates (ruff, mypy, coverage, security, complexity, dead code).

    This command executes all six industry-standard quality checks and reports results.
    """
    console.print("\n[bold blue]🔍 Running Quality Gates[/bold blue]\n")

    results = []

    # Gate 1: Ruff (Linting)
    console.print("[cyan]1/6 Running ruff...[/cyan]")
    ruff_result = _run_check(
        "ruff check src/",
        "Ruff Linting",
        fix_cmd="ruff check src/ --fix" if fix else None,
    )
    results.append(ruff_result)

    # Gate 2: MyPy (Type Checking)
    console.print("[cyan]2/6 Running mypy...[/cyan]")
    mypy_result = _run_check("mypy src/ --ignore-missing-imports", "MyPy Type Checking")
    results.append(mypy_result)

    # Gate 3: Pytest (Coverage)
    console.print("[cyan]3/6 Running pytest coverage...[/cyan]")
    coverage_result = _run_check(
        "pytest --cov=src --cov-report=term-missing --cov-fail-under=75 -q",
        "Test Coverage",
    )
    results.append(coverage_result)

    # Gate 4: pip-audit (Security)
    console.print("[cyan]4/6 Running pip-audit...[/cyan]")
    security_result = _run_check("pip-audit", "Security Audit")
    results.append(security_result)

    # Gate 5: Radon (Complexity)
    console.print("[cyan]5/6 Running radon complexity...[/cyan]")
    complexity_result = _run_check(
        "radon cc src/ -nc -a", "Complexity Analysis", is_warning=True
    )
    results.append(complexity_result)

    # Gate 6: Vulture (Dead Code)
    console.print("[cyan]6/6 Running vulture...[/cyan]")
    deadcode_result = _run_check(
        "vulture src/ --min-confidence 80", "Dead Code Detection", is_warning=True
    )
    results.append(deadcode_result)

    # Display Summary
    _display_summary(results, strict)

    # Exit with error if any critical gates failed
    critical_failures = [r for r in results if not r["passed"] and not r["is_warning"]]
    warning_failures = [r for r in results if not r["passed"] and r["is_warning"]]

    if critical_failures or (strict and warning_failures):
        raise typer.Exit(code=1)


def _run_check(
    command: str, name: str, fix_cmd: str | None = None, is_warning: bool = False
) -> dict:
    """Run a single quality check command."""
    try:
        # Try to fix first if fix_cmd provided
        if fix_cmd:
            subprocess.run(fix_cmd, shell=True, check=False, capture_output=True)

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, cwd=settings.REPO_PATH
        )

        passed = result.returncode == 0
        output_lines = (result.stdout + result.stderr).strip().split("\n")
        # Take last 3 lines for summary
        summary = "\n".join(output_lines[-3:]) if output_lines else "OK"

        return {
            "name": name,
            "passed": passed,
            "is_warning": is_warning,
            "summary": summary,
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {
            "name": name,
            "passed": False,
            "is_warning": is_warning,
            "summary": f"Error: {e}",
            "exit_code": -1,
        }


def _display_summary(results: list[dict], strict: bool) -> None:
    """Display results in a nice table."""
    console.print("\n[bold]Quality Gates Summary[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Summary", style="dim")

    for result in results:
        check_type = "WARNING" if result["is_warning"] else "ERROR"

        if result["passed"]:
            status = "[green]✓ PASS[/green]"
        elif result["is_warning"]:
            status = "[yellow]⚠ WARN[/yellow]"
        else:
            status = "[red]✗ FAIL[/red]"

        # Truncate summary to 60 chars
        summary = (
            result["summary"][:60] + "..."
            if len(result["summary"]) > 60
            else result["summary"]
        )

        table.add_row(result["name"], status, check_type, summary)

    console.print(table)

    # Overall status
    critical_fails = sum(1 for r in results if not r["passed"] and not r["is_warning"])
    warning_fails = sum(1 for r in results if not r["passed"] and r["is_warning"])

    if critical_fails == 0 and warning_fails == 0:
        console.print("\n[bold green]✅ All quality gates passed![/bold green]\n")
    elif critical_fails == 0:
        console.print(
            f"\n[bold yellow]⚠️  {warning_fails} warning(s) - review recommended[/bold yellow]\n"
        )
    else:
        console.print(
            f"\n[bold red]❌ {critical_fails} critical failure(s) - must fix before merge[/bold red]\n"
        )

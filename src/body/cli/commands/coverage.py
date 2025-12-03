# src/body/cli/commands/coverage.py
"""
CLI commands for test coverage management and autonomous remediation.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from features.self_healing.batch_remediation_service import _remediate_batch
from features.self_healing.coverage_remediation_service import _remediate_coverage
from mind.governance.checks.coverage_check import CoverageGovernanceCheck
from rich.console import Console
from rich.table import Table
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

logger = getLogger(__name__)
console = Console()
coverage_app = typer.Typer(
    help="Test coverage management and autonomous remediation.", no_args_is_help=True
)

# Removed: _context global and _ensure_context helper (handled by framework)


@coverage_app.command("check")
@core_command(dangerous=False)
# ID: 856e4881-14e7-4a5c-b2f9-d41453040992
async def check_coverage(ctx: typer.Context) -> None:
    """
    Checks current test coverage against constitutional requirements.
    Exits with code 1 if coverage is below the minimum threshold (75%).
    """
    console.print("[bold cyan]🔍 Checking Coverage Compliance...[/bold cyan]\n")

    core_context: CoreContext = ctx.obj

    # Inject auditor context
    checker = CoverageGovernanceCheck(core_context.auditor_context)
    findings = await checker.execute()

    if not findings:
        console.print(
            "[bold green]✅ Coverage meets constitutional requirements![/bold green]"
        )
        raise typer.Exit(code=0)

    console.print("[bold red]❌ Coverage Violations Found:[/bold red]\n")
    for finding in findings:
        console.print(f"  • {finding.message}")
        if finding.severity == "error":
            console.print(f"    [red]Severity: {finding.severity}[/red]")

    raise typer.Exit(code=1)


@coverage_app.command("report")
@core_command(dangerous=False)
# ID: 81a99734-ff1b-4330-9992-9fc3394fcbd4
def coverage_report(
    ctx: typer.Context,
    show_missing: bool = typer.Option(
        True,
        "--show-missing/--no-missing",
        help="Show line numbers of missing coverage",
    ),
    html: bool = typer.Option(False, "--html", help="Generate HTML coverage report"),
) -> None:
    """
    Generates a detailed coverage report.
    """
    # Context provided by framework, but we mostly need repo path here
    core_context: CoreContext = ctx.obj
    repo_path = core_context.git_service.repo_path

    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")
    try:
        cmd = ["coverage", "report"]
        if show_missing:
            cmd.append("--show-missing")
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Coverage report failed:[/red]\n{result.stderr}")
            raise typer.Exit(code=1)
        console.print(result.stdout)
        if html:
            html_result = subprocess.run(
                ["coverage", "html"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if html_result.returncode == 0:
                html_dir = repo_path / "htmlcov"
                console.print(
                    f"\n[bold green]✅ HTML report generated:[/bold green] {html_dir}/index.html"
                )
            else:
                console.print("[yellow]Warning: HTML generation failed[/yellow]")
    except FileNotFoundError:
        console.print(
            "[red]Error: coverage tool not found. Run: pip install coverage[/red]"
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("remediate")
@core_command(dangerous=True, confirmation=True)
# ID: d2c26a5f-21e3-4233-9c2d-cf9dfa18354c
async def remediate_coverage_cmd(
    ctx: typer.Context,
    file: Path = typer.Option(
        None,
        "--file",
        "-f",
        help="Target specific file for test generation (single-file mode)",
    ),
    count: int = typer.Option(
        None,
        "--count",
        "-n",
        help="Number of files to process (batch mode)",
        min=1,
        max=100,
    ),
    complexity: str = typer.Option(
        "moderate",
        "--complexity",
        "-c",
        help="Max complexity: simple, moderate, or complex",
    ),
    # Deprecated options kept for interface compatibility but ignored or passed through
    max_iterations: int = typer.Option(10, hidden=True),
    batch_size: int = typer.Option(5, hidden=True),
    write: bool = typer.Option(
        False, "--write", help="Write generated tests to filesystem"
    ),
) -> None:
    """
    Autonomously generates tests to restore constitutional coverage compliance.
    """
    core_context: CoreContext = ctx.obj

    complexity_lower = complexity.lower()
    if complexity_lower not in ["simple", "moderate", "complex"]:
        console.print(f"[red]Invalid complexity: {complexity}[/red]")
        raise typer.Exit(code=1)
    complexity_param = complexity_lower.upper()

    if file and count:
        console.print("[red]Error: Cannot use both --file and --count[/red]")
        raise typer.Exit(code=1)

    if file:
        console.print("[bold cyan]🎯 Single-File Coverage Remediation[/bold cyan]")
    elif count:
        console.print("[bold cyan]📦 Batch Coverage Remediation[/bold cyan]")
    else:
        console.print("[bold cyan]🤖 Full-Project Coverage Remediation[/bold cyan]")

    try:
        # JIT services are ready
        if count:
            result = await _remediate_batch(
                cognitive_service=core_context.cognitive_service,
                auditor_context=core_context.auditor_context,
                count=count,
                max_complexity=complexity_param,
            )
        else:
            result = await _remediate_coverage(
                cognitive_service=core_context.cognitive_service,
                auditor_context=core_context.auditor_context,
                target_coverage=None,
                file_path=file,
                max_complexity=complexity_param,
            )

        console.print("\n[bold]📊 Remediation Summary[/bold]")
        console.print(f"Status: {result.get('status')}")

        if result.get("status") == "completed" or result.get("status") == "success":
            console.print(
                "[bold green]✅ Test generation completed successfully[/bold green]"
            )
        else:
            console.print("[bold yellow]⚠️  Test generation had issues[/bold yellow]")
            if "error" in result:
                console.print(f"[dim]Error: {result['error']}[/dim]")

    except Exception as e:
        logger.error(f"Remediation failed: {e}", exc_info=True)
        console.print(f"[red]❌ Remediation failed: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("history")
@core_command(dangerous=False)
# ID: da398e37-3939-4883-bf9c-a16964415a54
def coverage_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of history entries to show"
    ),
) -> None:
    """
    Shows coverage history and trends over time.
    """
    core_context: CoreContext = ctx.obj
    history_file = (
        core_context.file_handler.repo_path
        / "work"
        / "testing"
        / "coverage_history.json"
    )

    if not history_file.exists():
        console.print("[yellow]No coverage history found[/yellow]")
        return

    try:
        history_data = json.loads(history_file.read_text())
        runs = history_data.get("runs", [])
        last_run = history_data.get("last_run", {})

        if not runs and not last_run:
            console.print("[yellow]History file is empty[/yellow]")
            return

        console.print("[bold]📈 Coverage History[/bold]\n")

        if last_run:
            console.print("[bold cyan]Latest Run:[/bold cyan]")
            console.print(f"  Timestamp: {last_run.get('timestamp', 'Unknown')}")
            console.print(f"  Overall:   {last_run.get('overall_percent', 0)}%")

        if runs:
            table = Table()
            table.add_column("Date", style="cyan")
            table.add_column("Coverage", justify="right", style="green")
            table.add_column("Delta", justify="right")

            for run in runs[-limit:]:
                delta = run.get("delta", 0)
                delta_color = "green" if delta >= 0 else "red"
                table.add_row(
                    run.get("timestamp", "Unknown"),
                    f"{run.get('overall_percent', 0)}%",
                    f"[{delta_color}]{delta:+.1f}%[/{delta_color}]",
                )
            console.print(table)

    except Exception as e:
        console.print(f"[red]Error reading history: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("target")
@core_command(dangerous=False)
# ID: 6d31e2a2-c0c3-4867-acc2-dae3e778cc2a
def show_targets(ctx: typer.Context) -> None:
    """
    Shows constitutional coverage requirements and targets.
    """
    console.print("[bold cyan]🎯 Coverage Targets[/bold cyan]\n")
    try:
        policy = settings.load("charter.policies.governance.quality_assurance_policy")
        config = policy.get("coverage_config", {}) or policy.get(
            "coverage_requirements", {}
        )

        console.print("[bold]Thresholds:[/bold]")
        console.print(f"  Minimum: {config.get('minimum_threshold', 75)}%")
        console.print(f"  Target:  {config.get('target_threshold', 80)}%\n")
    except Exception:
        console.print("[yellow]Could not load coverage policy.[/yellow]")


@coverage_app.command("accumulate")
@core_command(dangerous=True, confirmation=True)
# ID: e440b2d4-e4e4-4ba1-a276-6569f735e307
async def accumulate_tests_command(
    ctx: typer.Context,
    file_path: str = typer.Argument(
        ..., help="Source file to generate tests for (e.g., src/core/foo.py)"
    ),
    write: bool = typer.Option(
        False, "--write", help="Write generated tests to filesystem"
    ),
) -> None:
    """
    Generate tests for individual symbols, keep what works.
    """
    core_context: CoreContext = ctx.obj
    from features.self_healing.accumulative_test_service import (
        AccumulativeTestService,
    )

    service = AccumulativeTestService(core_context.cognitive_service)

    # Note: Accumulative service currently writes directly.
    # In a full migration, it should return an ActionResult.
    # For now, we allow it since dangerous=True protects us.
    result = await service.accumulate_tests_for_file(file_path)

    console.print("\n[bold]Results:[/bold]")
    console.print(f"  File: {result['file']}")
    console.print(f"  Success rate: {result['success_rate']:.0%}")


@coverage_app.command("accumulate-batch")
@core_command(dangerous=True, confirmation=True)
# ID: 7e941005-d150-479d-823b-cb728b6cf8c5
async def accumulate_batch_command(
    ctx: typer.Context,
    pattern: str = typer.Option(
        "src/**/*.py", help="Glob pattern for files to process"
    ),
    limit: int = typer.Option(10, help="Maximum number of files to process"),
    write: bool = typer.Option(
        False, "--write", help="Write generated tests to filesystem"
    ),
) -> None:
    """
    Generate tests for multiple files in batch (pragmatic approach).
    """
    core_context: CoreContext = ctx.obj
    from features.self_healing.accumulative_test_service import (
        AccumulativeTestService,
    )

    service = AccumulativeTestService(core_context.cognitive_service)
    files = list(settings.REPO_PATH.glob(pattern))[:limit]

    if not files:
        console.print(f"[yellow]No files found matching: {pattern}[/yellow]")
        return

    console.print(f"[cyan]Processing {len(files)} files...[/cyan]\n")

    total_tests = 0
    for file_path in files:
        rel_path = file_path.relative_to(settings.REPO_PATH)
        result = await service.accumulate_tests_for_file(str(rel_path))
        total_tests += result["tests_generated"]

    console.print(
        f"\n[bold green]Batch Complete! Generated {total_tests} tests.[/bold green]"
    )

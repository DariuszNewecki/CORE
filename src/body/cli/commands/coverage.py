# src/body/cli/commands/coverage.py

"""
CLI commands for test coverage management and autonomous remediation.

This implements the constitutional requirement that CORE maintains minimum
test coverage (75%) and autonomously heals when coverage drops below threshold.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import typer
from features.self_healing.batch_remediation_service import remediate_batch
from features.self_healing.coverage_remediation_service import remediate_coverage
from mind.governance.checks.coverage_check import CoverageGovernanceCheck
from rich.console import Console
from rich.table import Table
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

logger = getLogger(__name__)
console = Console()
coverage_app = typer.Typer(
    help="Test coverage management and autonomous remediation.", no_args_is_help=True
)
_context: CoreContext | None = None


def _ensure_context() -> CoreContext:
    """
    Ensure CoreContext is initialized.
    This is the missing function that caused the error!
    """
    global _context
    if _context is None:
        _context = CoreContext()
    return _context


@coverage_app.command("check")
# ID: c378a399-83ed-40b2-a177-b5345761f9ec
def check_coverage():
    """
    Checks current test coverage against constitutional requirements.

    This runs the coverage governance check and reports any violations.
    Exits with code 1 if coverage is below the minimum threshold (75%).
    """
    console.print("[bold cyan]🔍 Checking Coverage Compliance...[/bold cyan]\n")

    async def _async_check():
        checker = CoverageGovernanceCheck()
        findings = await checker.execute()
        if not findings:
            console.print(
                "[bold green]✅ Coverage meets constitutional requirements![/bold green]"
            )
            return 0
        console.print("[bold red]❌ Coverage Violations Found:[/bold red]\n")
        for finding in findings:
            console.print(f"  • {finding.message}")
            if finding.severity == "error":
                console.print(f"    [red]Severity: {finding.severity}[/red]")
        return 1

    exit_code = asyncio.run(_async_check())
    raise typer.Exit(code=exit_code)


@coverage_app.command("report")
# ID: cd808c91-3cd0-40bd-ba61-e9d8742e66c5
def coverage_report(
    show_missing: bool = typer.Option(
        True,
        "--show-missing/--no-missing",
        help="Show line numbers of missing coverage",
    ),
    html: bool = typer.Option(False, "--html", help="Generate HTML coverage report"),
):
    """
    Generates a detailed coverage report.

    By default, shows terminal output with missing lines.
    Use --html to generate an interactive HTML report in htmlcov/.
    """
    ctx = _ensure_context()
    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")
    try:
        cmd = ["coverage", "report"]
        if show_missing:
            cmd.append("--show-missing")
        result = subprocess.run(cmd, cwd=ctx.repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Coverage report failed:[/red]\n{result.stderr}")
            raise typer.Exit(code=1)
        console.print(result.stdout)
        if html:
            html_result = subprocess.run(
                ["coverage", "html"], cwd=ctx.repo_path, capture_output=True, text=True
            )
            if html_result.returncode == 0:
                html_dir = ctx.repo_path / "htmlcov"
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
# ID: 2b847514-44d9-4ba6-b597-6fc996707fc8
def remediate_coverage_cmd(
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
    max_iterations: int = typer.Option(
        10,
        "--max-iterations",
        help="Maximum remediation iterations (deprecated)",
        min=1,
        max=50,
    ),
    batch_size: int = typer.Option(
        5,
        "--batch-size",
        help="Modules to process per iteration (deprecated)",
        min=1,
        max=20,
    ),
    write: bool = typer.Option(
        False, "--write", help="Write generated tests to filesystem"
    ),
):
    """
    Autonomously generates tests to restore constitutional coverage compliance.

    Supports three modes:

    1. **Single-file mode** (--file): Generate tests for one specific module
       Example: --file src/core/git_service.py

    2. **Batch mode** (--count): Process N files automatically
       Example: --count 10 --complexity simple

    3. **Full-project mode** (default): Analyze entire codebase (deprecated)

    The process:
    1. Analyzes coverage gaps and creates a testing strategy
    2. Filters by complexity threshold (simple/moderate/complex)
    3. Generates tests using AI agents
    4. Validates and executes generated tests
    5. Reports results

    Examples:
        # Single file
        core-admin coverage remediate --file src/core/git_service.py

        # Batch: 5 simple files
        core-admin coverage remediate --count 5 --complexity simple

        # Batch: 10 moderate files
        core-admin coverage remediate --count 10 --complexity moderate
    """
    ctx = _ensure_context()
    complexity_lower = complexity.lower()
    if complexity_lower not in ["simple", "moderate", "complex"]:
        console.print(f"[red]Invalid complexity: {complexity}[/red]")
        console.print("Valid options: simple, moderate, complex")
        raise typer.Exit(code=1)
    complexity_param = complexity_lower.upper()
    if file and count:
        console.print("[red]Error: Cannot use both --file and --count[/red]")
        console.print("Use --file for single file, or --count for batch mode")
        raise typer.Exit(code=1)
    if file:
        console.print("[bold cyan]🎯 Single-File Coverage Remediation[/bold cyan]")
        console.print(f"   Target: {file}")
        console.print(f"   Complexity: {complexity_param}\n")
    elif count:
        console.print("[bold cyan]📦 Batch Coverage Remediation[/bold cyan]")
        console.print(f"   Files: {count}")
        console.print(f"   Complexity: {complexity_param}\n")
    else:
        console.print("[bold cyan]🤖 Full-Project Coverage Remediation[/bold cyan]")
        console.print(
            "[yellow]Note: Consider using --count for better control[/yellow]"
        )
        console.print(f"   Complexity: {complexity_param}\n")

    async def _async_remediate():
        try:
            if count:
                result = await remediate_batch(
                    cognitive_service=ctx.cognitive_service,
                    auditor_context=ctx.auditor_context,
                    count=count,
                    max_complexity=complexity_param,
                )
            else:
                result = await remediate_coverage(
                    cognitive_service=ctx.cognitive_service,
                    auditor_context=ctx.auditor_context,
                    target_coverage=None,
                    file_path=file,
                    max_complexity=complexity_param,
                )
            console.print("\n[bold]📊 Remediation Summary[/bold]")
            console.print(f"Total Tests: {result.get('total', 1)}")
            console.print(f"Succeeded: {result.get('succeeded', 0)}")
            console.print(f"Failed: {result.get('failed', 0)}")
            if "final_coverage" in result:
                console.print(f"Final Coverage: {result.get('final_coverage', 0):.1f}%")
            status = result.get("status")
            if status == "completed":
                console.print(
                    "\n[bold green]✅ Test generation completed successfully[/bold green]"
                )
                return 0
            else:
                console.print(
                    "\n[bold yellow]⚠️  Test generation had issues[/bold yellow]"
                )
                if "error" in result:
                    console.print(f"[dim]Error: {result['error']}[/dim]")
                return 1
        except Exception as e:
            logger.error(f"Remediation failed: {e}", exc_info=True)
            console.print(f"[red]❌ Remediation failed: {e}[/red]")
            return 1

    exit_code = asyncio.run(_async_remediate())
    raise typer.Exit(code=exit_code)


@coverage_app.command("history")
# ID: 9d3747a3-2fe1-4b20-8b0b-6afe0ca05dbb
def coverage_history(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of history entries to show"
    ),
):
    """
    Shows coverage history and trends over time.

    Displays historical coverage data from previous check runs,
    helping identify trends and regressions.
    """
    ctx = _ensure_context()
    history_file = ctx.repo_path / "work" / "testing" / "coverage_history.json"
    if not history_file.exists():
        console.print("[yellow]No coverage history found[/yellow]")
        console.print("   Run 'core-admin coverage check' to start tracking")
        return
    try:
        history_data = json.loads(history_file.read_text())
        runs = history_data.get("runs", [])
        last_run = history_data.get("last_run", {})
        if not runs and (not last_run):
            console.print("[yellow]History file is empty[/yellow]")
            return
        console.print("[bold]📈 Coverage History[/bold]\n")
        if last_run:
            console.print("[bold cyan]Latest Run:[/bold cyan]")
            console.print(f"  Timestamp: {last_run.get('timestamp', 'Unknown')}")
            console.print(f"  Overall Coverage: {last_run.get('overall_percent', 0)}%")
            console.print(
                f"  Lines Covered: {last_run.get('lines_covered', 0)}/{last_run.get('lines_total', 0)}"
            )
        if runs:
            console.print(
                f"\n[bold cyan]Previous Runs (last {min(limit, len(runs))}):[/bold cyan]"
            )
            table = Table()
            table.add_column("Date", style="cyan")
            table.add_column("Coverage", justify="right", style="green")
            table.add_column("Delta", justify="right")
            table.add_column("Lines", justify="right", style="dim")
            for run in runs[-limit:]:
                timestamp = run.get("timestamp", "Unknown")
                coverage = run.get("overall_percent", 0)
                delta = run.get("delta", 0)
                lines = f"{run.get('lines_covered', 0)}/{run.get('lines_total', 0)}"
                delta_color = "green" if delta >= 0 else "red"
                delta_str = f"[{delta_color}]{delta:+.1f}%[/{delta_color}]"
                table.add_row(timestamp, f"{coverage}%", delta_str, lines)
            console.print(table)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in history file: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error reading history: {e}[/red]")
        logger.error(f"History read failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


@coverage_app.command("target")
# ID: dd0beee4-4bfa-42e1-925f-6416ad0407b0
def show_targets():
    """
    Shows constitutional coverage requirements and targets.

    Displays the minimum and target thresholds defined in the
    quality_assurance_policy, along with critical paths that
    require higher coverage.
    """
    _ensure_context()
    console.print("[bold cyan]🎯 Coverage Targets[/bold cyan]\n")
    policy = settings.load("charter.policies.governance.quality_assurance_policy")
    config = policy.get("coverage_config", {})
    console.print("[bold]Thresholds:[/bold]")
    console.print(f"  Minimum: {config.get('minimum_threshold', 75)}%")
    console.print(f"  Target: {config.get('target_threshold', 80)}%\n")
    console.print("[bold]Critical Paths (Higher Requirements):[/bold]")
    for path_spec in config.get("critical_paths", []):
        console.print(f"  • {path_spec}")


@coverage_app.command("accumulate")
# ID: 8cc6cebd-3822-4d27-b4b4-f52276bfdc59
def accumulate_tests_command(
    file_path: str = typer.Argument(
        ..., help="Source file to generate tests for (e.g., src/core/foo.py)"
    ),
):
    """
    Generate tests for individual symbols, keep what works.

    This is the pragmatic approach: any successful test is a win.
    No complex strategies, just symbol-by-symbol accumulation.

    Philosophy: 40% success with simple approach > 30% with complex approach.

    Examples:
        core-admin coverage accumulate src/core/prompt_pipeline.py
        core-admin coverage accumulate src/shared/logger.py
    """

    async def _run():
        ctx = _ensure_context()
        from features.self_healing.accumulative_test_service import (
            AccumulativeTestService,
        )

        service = AccumulativeTestService(ctx.cognitive_service)
        result = await service.accumulate_tests_for_file(file_path)
        console.print("\n[bold]Results:[/bold]")
        console.print(f"  File: {result['file']}")
        console.print(f"  Success rate: {result['success_rate']:.0%}")
        console.print(
            f"  Tests generated: {result['tests_generated']}/{result['total_symbols']}"
        )
        if result["test_file"]:
            console.print(f"  Test file: {result['test_file']}")
        if result["failed_symbols"]:
            console.print("\n[yellow]Failed symbols (showing first 5):[/yellow]")
            for sym in result["failed_symbols"][:5]:
                console.print(f"  - {sym}")

    asyncio.run(_run())


@coverage_app.command("accumulate-batch")
# ID: aacd6c45-9f5d-495f-b0b4-2797287ae4ae
def accumulate_batch_command(
    pattern: str = typer.Option(
        "src/**/*.py", help="Glob pattern for files to process"
    ),
    limit: int = typer.Option(10, help="Maximum number of files to process"),
):
    """
    Generate tests for multiple files in batch (pragmatic approach).

    Uses simple symbol-by-symbol generation. Accumulates successful tests,
    skips failures. No complex strategies.

    Examples:
        core-admin coverage accumulate-batch --pattern "src/core/*.py" --limit 5
        core-admin coverage accumulate-batch --pattern "src/shared/*.py"
    """

    async def _run():
        ctx = _ensure_context()
        from features.self_healing.accumulative_test_service import (
            AccumulativeTestService,
        )

        service = AccumulativeTestService(ctx.cognitive_service)
        files = list(settings.REPO_PATH.glob(pattern))[:limit]
        if not files:
            console.print(f"[yellow]No files found matching: {pattern}[/yellow]")
            return
        console.print(f"[cyan]Processing {len(files)} files...[/cyan]\n")
        total_tests = 0
        total_symbols = 0
        for file_path in files:
            rel_path = file_path.relative_to(settings.REPO_PATH)
            result = await service.accumulate_tests_for_file(str(rel_path))
            total_tests += result["tests_generated"]
            total_symbols += result["total_symbols"]
        console.print("\n[bold green]Batch Complete![/bold green]")
        console.print(f"  Total tests generated: {total_tests}")
        console.print(f"  Total symbols attempted: {total_symbols}")
        if total_symbols > 0:
            console.print(
                f"  Overall success rate: {total_tests / total_symbols * 100:.0%}"
            )

    asyncio.run(_run())

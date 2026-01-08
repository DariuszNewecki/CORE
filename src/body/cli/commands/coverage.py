# src/body/cli/commands/coverage.py
# ID: 6e193f7f-14c1-4326-b040-ad6687887881

"""
CLI commands for test coverage management and autonomous remediation.
Aligned with Constitutional Rule Engine and Adaptive Test Generation (V2).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mind.governance.filtered_audit import run_filtered_audit
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()
coverage_app = typer.Typer(
    help="Test coverage management and autonomous remediation.", no_args_is_help=True
)


@coverage_app.command("check")
@core_command(dangerous=False)
# ID: 6e193f7f-14c1-4326-b040-ad6687887881
async def check_coverage(ctx: typer.Context) -> None:
    """
    Checks current test coverage against constitutional requirements.
    Uses the 'qa.coverage.*' dynamic rule set from the Mind.
    """
    console.print(
        "[bold cyan]🔍 Checking Coverage Compliance via Constitution...[/bold cyan]\n"
    )
    core_context: CoreContext = ctx.obj

    # Uses the core filtered audit mechanism to check against active policies
    findings, _executed, _stats = await run_filtered_audit(
        core_context.auditor_context, rule_patterns=[r"qa\.coverage\..*"]
    )

    if not findings:
        console.print(
            "[bold green]✅ Coverage meets all constitutional requirements![/bold green]"
        )
        return

    blocking_violations = [f for f in findings if f.get("severity") == "error"]

    console.print(
        f"[bold red]❌ Found {len(findings)} Coverage Violations:[/bold red]\n"
    )

    for finding in findings:
        msg = finding.get("message", "Unknown violation")
        severity = finding.get("severity", "warning")
        color = "red" if severity == "error" else "yellow"
        console.print(f"  • [{color}]{severity.upper()}[/{color}] {msg}")

    if blocking_violations:
        console.print("\n[dim]Audit FAILED due to blocking errors.[/dim]")
        raise typer.Exit(code=1)


@coverage_app.command("report")
@core_command(dangerous=False)
# ID: b2c5d852-3d18-4d06-939e-b18883e7c757
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
    Generates a detailed coverage report from local .coverage data.
    """
    core_context: CoreContext = ctx.obj
    repo_path = core_context.git_service.repo_path

    # CONSTITUTIONAL FIX: Fail fast if data is missing
    if not (repo_path / ".coverage").exists():
        console.print(
            "[yellow]⚠️ No coverage data found. Run 'poetry run pytest --cov=src' first.[/yellow]"
        )
        raise typer.Exit(0)

    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")
    try:
        # CONSTITUTIONAL FIX: Use 'poetry run' to ensure environment stability
        cmd = ["poetry", "run", "coverage", "report"]
        if show_missing:
            cmd.append("--show-missing")

        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)

        if result.returncode != 0:
            # Capture stdout too (coverage often puts 'No data' messages there)
            error_msg = result.stderr or result.stdout or "Unknown failure"
            console.print(f"[red]Coverage report failed:[/red]\n{error_msg}")
            raise typer.Exit(code=1)

        console.print(result.stdout)

        if html:
            html_result = subprocess.run(
                ["poetry", "run", "coverage", "html"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if html_result.returncode == 0:
                html_dir = repo_path / "htmlcov"
                console.print(
                    f"\n[bold green]✅ HTML report generated:[/bold green] {html_dir}/index.html"
                )
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
# ID: b5a5fd3f-40df-45f5-b590-c0d158a7b7e4
async def remediate_coverage_cmd(
    ctx: typer.Context,
    file: Path = typer.Option(
        None,
        "--file",
        "-f",
        help="Target specific file for test generation",
    ),
    count: int = typer.Option(
        None,
        "--count",
        "-n",
        help="Number of files to process (batch mode)",
    ),
    complexity: str = typer.Option(
        "moderate",
        "--complexity",
        "-c",
        help="Max complexity: simple, moderate, or complex",
    ),
) -> None:
    """
    Autonomously generates tests to restore constitutional coverage compliance.
    (Legacy interface for Batch/Auto remediation)
    """
    # CONSTITUTIONAL FIX: Lazy-loading to prevent boot-time ModuleNotFoundError
    from features.self_healing.batch_remediation_service import _remediate_batch
    from features.self_healing.coverage_remediation_service import _remediate_coverage

    core_context: CoreContext = ctx.obj
    complexity_param = complexity.upper()

    if file and count:
        console.print("[red]Error: Cannot use both --file and --count[/red]")
        raise typer.Exit(code=1)

    try:
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
        status = result.get("status")
        if status in ("completed", "success"):
            console.print(
                "[bold green]✅ Remediation successfully completed[/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]⚠️  Remediation finished with status: {status}[/bold yellow]"
            )
            if "error" in result:
                console.print(f"[dim]Detail: {result['error']}[/dim]")
    except Exception as e:
        logger.error("Remediation failed: %s", e, exc_info=True)
        console.print(f"[red]❌ Remediation failed: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("history")
@core_command(dangerous=False)
# ID: f69d0e59-11bb-4607-9ba1-5e35060c2e3c
def coverage_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of history entries to show"
    ),
) -> None:
    """
    Shows coverage history and trends from the Mind's history records.
    """
    core_context: CoreContext = ctx.obj
    history_file = (
        core_context.file_handler.repo_path
        / "var"
        / "mind"
        / "history"
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
            console.print(
                f"  Latest Run: [cyan]{last_run.get('overall_percent', 0)}%[/cyan]"
            )

        if runs:
            table = Table(box=None)
            table.add_column("Date", style="dim")
            table.add_column("Coverage", justify="right")
            table.add_column("Delta", justify="right")
            for run in runs[-limit:]:
                delta = run.get("delta", 0)
                color = "green" if delta >= 0 else "red"
                table.add_row(
                    run.get("timestamp", "Unknown")[:16],
                    f"{run.get('overall_percent', 0)}%",
                    f"[{color}]{delta:+.1f}%[/{color}]",
                )
            console.print(table)
    except Exception as e:
        console.print(f"[red]Error reading history: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("target")
@core_command(dangerous=False)
# ID: 5a11f3db-0510-4f00-9cb2-14801a5f269f
def show_targets(ctx: typer.Context) -> None:
    """
    Shows constitutional coverage targets directly from the quality_assurance policy.
    """
    console.print("[bold cyan]🎯 Constitutional Coverage Targets[/bold cyan]\n")
    try:
        policy_path = settings.paths.policy("quality_assurance")
        content = policy_path.read_text(encoding="utf-8")
        data = json.loads(content) if policy_path.suffix == ".json" else {}

        rules = data.get("rules", [])

        for rule in rules:
            rule_id = rule.get("id", "")
            if "coverage" in rule_id:
                status = (
                    "blocking" if rule.get("enforcement") == "error" else "guideline"
                )
                console.print(f"  • [bold]{rule_id}[/bold] ({status})")
                console.print(f"    [dim]{rule.get('statement')}[/dim]\n")

    except Exception:
        console.print("[yellow]Could not load coverage policy from the Mind.[/yellow]")


@coverage_app.command("accumulate")
@core_command(dangerous=True, confirmation=True)
# ID: 7edff4e6-b383-47b3-8cf1-c502ba9a2d9a
async def accumulate_tests_command(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="Source file"),
    write: bool = typer.Option(False, "--write", help="Persist results to filesystem"),
) -> None:
    """
    (Legacy V1) Generate tests for individual symbols, keeping only what passes.
    """
    # CONSTITUTIONAL FIX: Lazy-loading to prevent boot-time ModuleNotFoundError
    from features.self_healing.accumulative_test_service import AccumulativeTestService

    core_context: CoreContext = ctx.obj
    service = AccumulativeTestService(core_context.cognitive_service)
    result = await service.accumulate_tests_for_file(file_path, write=write)

    console.print("\n[bold]Accumulation Results:[/bold]")
    console.print(f"  File: {result['file']}")
    console.print(f"  Success rate: {result['success_rate']:.0%}")
    console.print(f"  Tests kept: {result['tests_generated']}")


@coverage_app.command("accumulate-batch")
@core_command(dangerous=True, confirmation=True)
# ID: 0d846e3f-843a-463e-9355-f58c3c7bf214
async def accumulate_batch_command(
    ctx: typer.Context,
    pattern: str = typer.Option("src/**/*.py", help="File pattern"),
    limit: int = typer.Option(10, help="Max files"),
    write: bool = typer.Option(False, "--write", help="Persist results"),
) -> None:
    """
    (Legacy V1) Run symbol-by-symbol test accumulation across multiple files.
    """
    # CONSTITUTIONAL FIX: Lazy-loading
    from features.self_healing.accumulative_test_service import AccumulativeTestService
    from features.self_healing.coverage_analyzer import CoverageAnalyzer

    core_context: CoreContext = ctx.obj
    service = AccumulativeTestService(core_context.cognitive_service)
    analyzer = CoverageAnalyzer()
    coverage_map = analyzer.get_module_coverage()

    all_files = list(settings.REPO_PATH.glob(pattern))

    # ID: 353ee414-4202-490c-8be8-fa6d7942d737
    def get_coverage_score(file_path: Path) -> float:
        try:
            rel = str(file_path.relative_to(settings.REPO_PATH)).replace("\\", "/")
            return float(coverage_map.get(rel, 0.0))
        except (ValueError, KeyError):
            return 0.0

    prioritized_files = sorted(all_files, key=get_coverage_score)[:limit]

    if not prioritized_files:
        console.print(f"[yellow]No files found matching: {pattern}[/yellow]")
        return

    console.print(
        f"[cyan]Processing {len(prioritized_files)} files (Lowest Coverage First)...[/cyan]\n"
    )
    total_tests = 0
    for file_path in prioritized_files:
        rel_path = file_path.relative_to(settings.REPO_PATH)
        result = await service.accumulate_tests_for_file(str(rel_path), write=write)
        total_tests += result.get("tests_generated", 0)

    console.print(
        f"\n[bold green]Batch Complete! Accumulated {total_tests} new tests.[/bold green]"
    )


@coverage_app.command("generate-adaptive")
@core_command(dangerous=True, confirmation=True)
# ID: a7d1c24e-3f5b-4b1a-9d2c-8e4f1a2b3c4d
async def generate_adaptive_command(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="Source file to generate tests for"),
    write: bool = typer.Option(
        False,
        "--write",
        help="Promote sandbox-passing tests to /tests (mirror src/). Route failures to var/artifacts/.",
    ),
    max_failures: int = typer.Option(
        3, "--max-failures", help="Switch strategy after N failures with same pattern"
    ),
) -> None:
    """
    Generate tests using adaptive learning (V2 - Component Architecture).

    Delivery model (when --write is used):
    - Passing sandbox tests are promoted to mirrored paths under /tests (Verified Truth).
    - Failing sandbox tests are quarantined under var/artifacts/test_gen/failures/ (Morgue).
    """
    # CONSTITUTIONAL FIX: Lazy-loading to support new V2 engine
    from features.test_generation_v2 import AdaptiveTestGenerator, TestGenerationResult

    core_context: CoreContext = ctx.obj

    console.print("[bold cyan]🧪 Adaptive Test Generation (V2)[/bold cyan]\n")

    try:
        generator = AdaptiveTestGenerator(context=core_context)

        result: TestGenerationResult = await generator.generate_tests_for_file(
            file_path=file_path,
            write=write,
            max_failures_per_pattern=max_failures,
        )

        sandbox_passed = getattr(result, "sandbox_passed", None)

        console.print("\n[bold]📊 Generation Results:[/bold]")
        console.print(f"  File: {result.file_path}")
        console.print(f"  Total symbols: {result.total_symbols}")

        # Interpret counts with Promotion/Morgue semantics
        console.print(f"  Validated tests: {result.tests_generated}")
        if sandbox_passed is not None:
            console.print(f"  Sandbox passed: {sandbox_passed}")
        console.print(f"  Sandbox failed: {result.tests_failed}")
        console.print(f"  Skipped: {result.tests_skipped}")

        rate_color = "green" if result.success_rate > 0.5 else "yellow"
        console.print(
            f"  Validation rate: [{rate_color}]{result.success_rate:.1%}[/{rate_color}]"
        )

        if result.strategy_switches > 0:
            console.print(
                f"  Strategy switches: [cyan]{result.strategy_switches}[/cyan]"
            )

        if result.patterns_learned:
            console.print("\n[bold]🧠 Patterns Learned:[/bold]")
            for pattern, count in sorted(
                result.patterns_learned.items(), key=lambda x: x[1], reverse=True
            ):
                console.print(f"  • {pattern}: {count}x")

        console.print(f"\n⏱️  Duration: {result.total_duration:.2f}s")

        if write:
            console.print("\n[dim]Write mode:[/dim]")
            console.print("  • Passing tests -> tests/... (mirrored)")
            console.print("  • Failing tests  -> var/artifacts/test_gen/failures/...")

        if result.tests_generated > 0:
            console.print("\n[bold green]✅ Completed generation cycle.[/bold green]")
        else:
            console.print(
                "\n[bold yellow]⚠️  No tests validated successfully.[/bold yellow]"
            )

    except Exception as e:
        logger.error("Adaptive test generation failed: %s", e, exc_info=True)
        console.print(f"[red]❌ Generation failed: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("compare-methods")
@core_command(dangerous=False)
# ID: 3b9c1d2e-4f5a-6b7c-8d9e-0f1a2b3c4d5e
async def compare_methods_command(ctx: typer.Context) -> None:
    """
    Compare legacy (accumulate) vs new (adaptive) test generation methods.
    """
    comparison_text = (
        "[bold]OLD: Accumulative (V1)[/bold]\n"
        "  Architecture: Monolithic (~800 lines)\n"
        "  Learning: None (repeats same mistakes)\n"
        "  Strategy: Fixed\n"
        "  Success rate: ~0% on complex files\n\n"
        "[bold]NEW: Adaptive (V2)[/bold]\n"
        "  Architecture: Component-based (6 small components)\n"
        "  Learning: Pattern recognition (switches after 3 failures)\n"
        "  Strategy: Adaptive (file-type aware)\n"
        "  Success rate: ~57% on complex files\n\n"
        "[bold]Key Improvements:[/bold]\n"
        "  ✓ File analysis before generation\n"
        "  ✓ Failure pattern recognition\n"
        "  ✓ Automatic strategy switching"
    )

    console.print(
        Panel(
            comparison_text,
            title="📊 Method Comparison",
            border_style="cyan",
            expand=False,
        )
    )

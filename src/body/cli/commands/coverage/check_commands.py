# src/body/cli/commands/coverage/check_commands.py
"""
Coverage checking and reporting commands.

Constitutional Alignment:
- Uses CoreContext for repo_path and policy access (no direct settings access)
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: da09f646-d657-47af-a28f-f9c72f59c797
def register_check_commands(app: typer.Typer) -> None:
    """Register coverage check and report commands."""
    app.command("check")(check_coverage)
    app.command("report")(coverage_report)
    app.command("target")(show_targets)
    app.command("gaps")(show_coverage_gaps)


@core_command(dangerous=False)
# ID: 6e193f7f-14c1-4326-b040-ad6687887881
async def check_coverage(ctx: typer.Context) -> None:
    """
    Checks current test coverage against constitutional requirements.
    Uses the 'qa.coverage.*' dynamic rule set from the Mind.
    """
    from .services import CoverageChecker

    console.print(
        "[bold cyan]🔍 Checking Coverage Compliance via Constitution...[/bold cyan]\n"
    )
    core_context: CoreContext = ctx.obj

    checker = CoverageChecker(core_context.auditor_context)
    result = await checker.check_compliance()

    if result["compliant"]:
        console.print(
            "[bold green]✅ Coverage meets all constitutional requirements![/bold green]"
        )
        return

    findings = result["findings"]
    blocking_violations = result["blocking_violations"]

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
    from .services import CoverageReporter

    core_context: CoreContext = ctx.obj
    reporter = CoverageReporter(core_context.git_service.repo_path)

    # Check if coverage data exists
    if not reporter.has_coverage_data():
        console.print(
            "[yellow]⚠️ No coverage data found. Run 'poetry run pytest --cov=src' first.[/yellow]"
        )
        raise typer.Exit(0)

    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")

    try:
        # Generate text report
        output = reporter.generate_text_report(show_missing=show_missing)
        console.print(output)

        # Generate HTML if requested
        if html:
            html_dir = reporter.generate_html_report()
            console.print(
                f"\n[bold green]✅ HTML report generated:[/bold green] {html_dir}/index.html"
            )

    except FileNotFoundError:
        console.print(
            "[red]Error: coverage tool not found. Run: pip install coverage[/red]"
        )
        raise typer.Exit(code=1)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        raise typer.Exit(code=1)


@core_command(dangerous=False)
# ID: 5a11f3db-0510-4f00-9cb2-14801a5f269f
def show_targets(ctx: typer.Context) -> None:
    """
    Shows constitutional coverage targets directly from the quality_assurance policy.

    Constitutional Compliance:
    - Accesses policy files through Intent system (not direct settings.paths)
    """
    console.print("[bold cyan]🎯 Constitutional Coverage Targets[/bold cyan]\n")

    core_context: CoreContext = ctx.obj

    try:
        # Constitutional: Construct policy path from repo root
        repo_root = core_context.git_service.repo_path
        policy_path = repo_root / ".intent" / "policies" / "quality_assurance.json"

        if not policy_path.exists():
            console.print(
                "[yellow]Quality assurance policy not found in .intent/policies/[/yellow]"
            )
            return

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

    except Exception as e:
        logger.error("Error loading coverage policy: %s", e, exc_info=True)
        console.print("[yellow]Could not load coverage policy from the Mind.[/yellow]")


@core_command(dangerous=False)
# ID: 8f1e2d3c-4a5b-6c7d-8e9f-0a1b2c3d4e5f
async def show_coverage_gaps(ctx: typer.Context) -> None:
    """
    Shows files/modules with insufficient coverage (gaps analysis).
    """
    from .services import GapsAnalyzer

    console.print("[bold cyan]📉 Coverage Gaps Analysis[/bold cyan]\n")

    try:
        analyzer = GapsAnalyzer()
        gaps = analyzer.find_gaps(threshold=75.0)

        if not gaps["sorted_lowest"]:
            console.print(
                "[yellow]No coverage data. Run 'poetry run pytest --cov=src' first.[/yellow]"
            )
            return

        # Display lowest coverage modules
        table = Table(title="Lowest Coverage Modules (Bottom 20)")
        table.add_column("Module", style="cyan")
        table.add_column("Coverage", justify="right")

        for module, coverage in gaps["sorted_lowest"]:
            color = "red" if coverage < 50 else "yellow" if coverage < 75 else "green"
            table.add_row(module, f"[{color}]{coverage:.1f}%[/{color}]")

        console.print(table)

        # Summary stats
        stats = gaps["stats"]
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Total modules: {stats['total']}")
        console.print(
            f"  Below {stats['threshold']}%: {stats['below_threshold']} ({stats['below_threshold']/stats['total']*100:.1f}%)"
        )
        console.print(
            f"  Below 50%: {stats['below_50']} ({stats['below_50']/stats['total']*100:.1f}%)"
        )

    except Exception as e:
        logger.error("Gaps analysis failed: %s", e, exc_info=True)
        console.print(f"[red]Error analyzing gaps: {e}[/red]")
        raise typer.Exit(code=1)

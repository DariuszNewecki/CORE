# src/cli/commands/coverage/check_commands.py
"""
Coverage checking and reporting commands.

Constitutional Alignment:
- Uses CoreContext for repo_path and policy access (no direct settings access)
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: 72963da2-9a25-487b-92ee-0d67a6d1376d
def register_check_commands(app: typer.Typer) -> None:
    """Register coverage check and report commands."""
    app.command("check")(check_coverage)
    app.command("report")(coverage_report)
    app.command("target")(show_targets)
    app.command("gaps")(show_coverage_gaps)


@core_command(dangerous=False)
# ID: cbec039a-f2aa-4fc8-9a24-d7e2ba4ef15c
async def check_coverage(ctx: typer.Context) -> None:
    """
    Checks current test coverage against constitutional requirements.
    Uses the 'qa.coverage.*' dynamic rule set from the Mind.
    """
    from .services import CoverageChecker

    logger.info(
        "[bold cyan]🔍 Checking Coverage Compliance via Constitution...[/bold cyan]\n"
    )
    core_context: CoreContext = ctx.obj
    checker = CoverageChecker(core_context.auditor_context)
    result = await checker.check_compliance()
    if result["compliant"]:
        logger.info(
            "[bold green]✅ Coverage meets all constitutional requirements![/bold green]"
        )
        return
    findings = result["findings"]
    blocking_violations = result["blocking_violations"]
    logger.info(
        "[bold red]❌ Found %s Coverage Violations:[/bold red]\n", len(findings)
    )
    for finding in findings:
        msg = finding.get("message", "Unknown violation")
        severity = finding.get("severity", "warning")
        color = "red" if severity == "error" else "yellow"
        logger.info("  • [%s]%s[/%s] %s", color, severity.upper(), color, msg)
    if blocking_violations:
        logger.info("\n[dim]Audit FAILED due to blocking errors.[/dim]")
        raise typer.Exit(code=1)


@core_command(dangerous=False)
# ID: 99932c42-c4d5-48ec-aa00-cd4beb3971e8
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
    if not reporter.has_coverage_data():
        logger.info(
            "[yellow]⚠️ No coverage data found. Run 'poetry run pytest --cov=src' first.[/yellow]"
        )
        raise typer.Exit(0)
    logger.info("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")
    try:
        output = reporter.generate_text_report(show_missing=show_missing)
        logger.info(output)
        if html:
            html_dir = reporter.generate_html_report()
            logger.info(
                "\n[bold green]✅ HTML report generated:[/bold green] %s/index.html",
                html_dir,
            )
    except FileNotFoundError:
        logger.info(
            "[red]Error: coverage tool not found. Run: pip install coverage[/red]"
        )
        raise typer.Exit(code=1)
    except RuntimeError as e:
        logger.info("[red]%s[/red]", e)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.info("[red]Error generating report: %s[/red]", e)
        raise typer.Exit(code=1)


@core_command(dangerous=False)
# ID: d0e8d322-d374-42ce-9150-70c158f05297
def show_targets(ctx: typer.Context) -> None:
    """
    Shows constitutional coverage targets directly from the quality_gates policy.

    Constitutional Compliance:
    - Accesses policy files through IntentRepository (not direct filesystem access)
    """
    logger.info("[bold cyan]🎯 Constitutional Coverage Targets[/bold cyan]\n")
    core_context: CoreContext = ctx.obj
    try:
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        repo = get_intent_repository()
        data = repo.load_policy("rules/architecture/quality_gates")
        rules = data.get("rules", [])
        for rule in rules:
            rule_id = rule.get("id", "")
            if "coverage" in rule_id:
                status = (
                    "blocking" if rule.get("enforcement") == "error" else "guideline"
                )
                logger.info("  • [bold]%s[/bold] (%s)", rule_id, status)
                logger.info("    [dim]%s[/dim]\n", rule.get("statement"))
        if not any("coverage" in r.get("id", "") for r in rules):
            logger.info(
                "[yellow]No coverage rules found in quality_gates policy.[/yellow]"
            )
    except Exception as e:
        logger.error("Error loading coverage policy: %s", e, exc_info=True)
        logger.info("[yellow]Could not load coverage policy from the Mind.[/yellow]")


@core_command(dangerous=False)
# ID: f9b4da0d-deca-4641-8bf5-baa906f1ade4
async def show_coverage_gaps(ctx: typer.Context) -> None:
    """
    Shows files/modules with insufficient coverage (gaps analysis).
    """
    from .services import GapsAnalyzer

    logger.info("[bold cyan]📉 Coverage Gaps Analysis[/bold cyan]\n")
    try:
        core_context: CoreContext = ctx.obj
        analyzer = GapsAnalyzer(repo_root=core_context.git_service.repo_path)
        gaps = analyzer.find_gaps(threshold=75.0)
        if not gaps["sorted_lowest"]:
            logger.info(
                "[yellow]No coverage data. Run 'poetry run pytest --cov=src' first.[/yellow]"
            )
            return
        table = Table(title="Lowest Coverage Modules (Bottom 20)")
        table.add_column("Module", style="cyan")
        table.add_column("Coverage", justify="right")
        for module, coverage in gaps["sorted_lowest"]:
            color = "red" if coverage < 50 else "yellow" if coverage < 75 else "green"
            table.add_row(module, f"[{color}]{coverage:.1f}%[/{color}]")
        logger.info(table)
        stats = gaps["stats"]
        logger.info("\n[bold]Summary:[/bold]")
        logger.info("  Total modules: %s", stats["total"])
        logger.info(
            "  Below %s%: %s (%s%)",
            stats["threshold"],
            stats["below_threshold"],
            stats["below_threshold"] / stats["total"] * 100,
        )
        logger.info(
            "  Below 50%: %s (%s%)",
            stats["below_50"],
            stats["below_50"] / stats["total"] * 100,
        )
    except Exception as e:
        logger.error("Gaps analysis failed: %s", e, exc_info=True)
        logger.info("[red]Error analyzing gaps: %s[/red]", e)
        raise typer.Exit(code=1)

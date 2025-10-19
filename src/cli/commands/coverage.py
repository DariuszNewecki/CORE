# src/cli/commands/coverage.py
"""
CLI commands for test coverage management and autonomous remediation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path  # <--- ADDED

import typer
from core.cognitive_service import CognitiveService
from features.governance.audit_context import AuditorContext
from features.governance.checks.coverage_check import CoverageGovernanceCheck
from features.self_healing.coverage_remediation_service import remediate_coverage
from rich.console import Console
from shared.context import CoreContext
from shared.logger import getLogger

log = getLogger(__name__)
console = Console()

coverage_app = typer.Typer(
    help="Test coverage management and autonomous remediation.",
    no_args_is_help=True,
)

_context: CoreContext | None = None


@coverage_app.command("check")
# ID: 83bb5cd2-c6a0-486c-8768-f54e9d45c5b2
def check_coverage():
    """
    Checks current test coverage against constitutional requirements.

    This runs the coverage governance check and reports any violations.
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

        console.print(
            f"[bold red]❌ Found {len(findings)} coverage violations:[/bold red]\n"
        )

        for finding in findings:
            severity_color = {
                "error": "red",
                "warn": "yellow",
                "info": "blue",
            }.get(finding.severity, "white")

            console.print(f"[{severity_color}]▸ {finding.message}[/{severity_color}]")

            if finding.context:
                console.print(f"  [dim]{finding.context}[/dim]")

        # Return non-zero exit code if errors found
        has_errors = any(f.severity == "error" for f in findings)
        return 1 if has_errors else 0

    exit_code = asyncio.run(_async_check())
    raise typer.Exit(code=exit_code)


@coverage_app.command("report")
# ID: a7d030b1-57d0-4461-9db1-5364b0a24135
def coverage_report(
    html: bool = typer.Option(False, "--html", help="Generate HTML coverage report"),
    show_missing: bool = typer.Option(
        True, "--show-missing/--no-show-missing", help="Show lines missing coverage"
    ),
):
    """
    Generates a detailed test coverage report.

    By default, shows terminal output. Use --html for interactive HTML report.
    """
    import subprocess

    from shared.config import settings

    console.print("[bold cyan]📊 Generating Coverage Report...[/bold cyan]\n")

    cmd = ["poetry", "run", "pytest", "--cov=src", "--cov-report=term"]

    if html:
        cmd.append("--cov-report=html")

    if show_missing:
        cmd.append("--cov-report=term-missing")

    result = subprocess.run(
        cmd,
        cwd=settings.REPO_PATH,
        capture_output=True,
        text=True,
    )

    console.print(result.stdout)

    if html:
        html_path = settings.REPO_PATH / "htmlcov" / "index.html"
        if html_path.exists():
            console.print(f"\n[green]📄 HTML report generated: {html_path}[/green]")
            console.print(f"   Open in browser: file://{html_path.absolute()}")

    if result.returncode != 0:
        console.print(
            f"\n[yellow]⚠️  Coverage command exited with code {result.returncode}[/yellow]"
        )


@coverage_app.command("remediate")
# ID: 26a19b9d-154b-4ba1-b99d-003c07c522b7
def remediate_coverage_command(
    ctx: typer.Context,
    target: int | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Target coverage percentage to reach (default: 75% constitutional minimum)",
        min=0,
        max=100,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview strategy without generating tests"
    ),
    # --- START OF OUR ADDITION ---
    file: Path | None = typer.Option(
        None,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Remediate a single specific file instead of the whole project.",
    ),
    # --- END OF OUR ADDITION ---
):
    """
    Autonomously generates tests to restore constitutional coverage compliance.
    ... (docstring unchanged) ...
    """
    core_context: CoreContext = ctx.obj

    console.print(
        "[bold cyan]🤖 Initiating Autonomous Coverage Remediation[/bold cyan]"
    )
    # --- MODIFIED to display the correct mode ---
    if file:
        from shared.config import settings

        console.print(f"   Target File: {file.relative_to(settings.REPO_PATH)}")
    else:
        if target is None:
            target = 75  # Default to constitutional minimum if not specified
        console.print(f"   Target: {target}% coverage")

    console.print("[dim]This may take several minutes...[/dim]\n")

    async def _async_remediate():
        from shared.config import settings

        cognitive = CognitiveService(settings.REPO_PATH)
        auditor = AuditorContext(settings.REPO_PATH)

        # --- MODIFIED to pass the new 'file' argument ---
        result = await remediate_coverage(
            cognitive, auditor, target_coverage=target, file_path=file
        )

        if result.get("status") == "completed":
            console.print(
                "\n[bold green]✅ Remediation completed successfully![/bold green]"
            )
            final_coverage = result.get("final_coverage", 0)
            if file:
                console.print(f"   Final Project Coverage: {final_coverage}%")
            elif target and final_coverage >= target:
                console.print(
                    f"   Coverage: {final_coverage}% [green]✓ Target reached[/green]"
                )
            else:
                console.print(
                    f"   Coverage: {final_coverage}% [yellow]⚠️  Below target ({target}%)[/yellow]"
                )
        else:
            console.print("\n[yellow]⚠️  Remediation incomplete[/yellow]")

        return result

    if dry_run:
        console.print("[yellow]Dry-run mode not yet implemented[/yellow]")
        return

    result = asyncio.run(_async_remediate())

    if result.get("status") != "completed":
        raise typer.Exit(code=1)


@coverage_app.command("history")
# ID: e8f5a2c3-9d1b-4f6e-a5c7-8b3d2e4f1a6c
def coverage_history(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of historical entries to show"
    ),
):
    """
    Shows coverage history and trends over time.
    """

    from shared.config import settings

    history_file = settings.REPO_PATH / "work" / "testing" / "coverage_history.json"

    if not history_file.exists():
        console.print("[yellow]No coverage history found[/yellow]")
        console.print("   Run 'core-admin coverage check' to start tracking")
        return

    try:
        import json

        history = json.loads(history_file.read_text())
        last_run = history.get("last_run", {})

        console.print("[bold]📈 Coverage History[/bold]\n")
        console.print(f"Last Updated: {last_run.get('timestamp', 'Unknown')}")
        console.print(f"Overall Coverage: {last_run.get('overall_percent', 0)}%")
        console.print(
            f"Lines Covered: {last_run.get('lines_covered', 0)}/{last_run.get('lines_total', 0)}"
        )

    except Exception as e:
        console.print(f"[red]Error reading history: {e}[/red]")
        raise typer.Exit(code=1)


@coverage_app.command("target")
# ID: b2c4d6e8-f1a3-5b7c-9d2e-4f6a8c1b3e5d
def show_targets():
    """
    Shows constitutional coverage requirements and targets.
    """
    from shared.config import settings

    policy = settings.load("charter.policies.governance.quality_assurance_policy")
    config = policy.get("coverage_config", {})

    console.print("[bold]🎯 Coverage Targets[/bold]\n")
    console.print(f"Minimum Threshold: {config.get('minimum_threshold', 75)}%")
    console.print(f"Target Threshold: {config.get('target_threshold', 80)}%\n")

    critical_paths = config.get("critical_paths", [])
    if critical_paths:
        console.print("[bold]Critical Paths (Higher Requirements):[/bold]")
        for path_spec in critical_paths:
            console.print(f"  • {path_spec}")

    console.print(
        "\n[dim]Defined in: .intent/charter/policies/governance/quality_assurance__policy.yaml[/dim]"
    )

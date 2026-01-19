# src/body/cli/commands/refactor.py

"""
Refactoring analysis commands - identify modularization opportunities.

Constitutional enforcement of modularity rules:
- Single responsibility
- Semantic cohesion
- Import coupling
- Comprehensive refactor scoring

This module pulls its thresholds directly from the Constitution (.intent).
"""

from __future__ import annotations

import typer

from body.cli.commands.refactor_support.analyzer import RefactorAnalyzer
from body.cli.commands.refactor_support.config import (
    get_modularity_threshold,
    get_source_files,
)
from body.cli.commands.refactor_support.display import RefactorDisplay
from body.cli.commands.refactor_support.recommendations import RecommendationEngine
from shared.cli_utils import core_command
from shared.config import settings


refactor_app = typer.Typer(
    help="Refactoring analysis and suggestions", no_args_is_help=True
)


@refactor_app.command("analyze")
@core_command(dangerous=False)
# ID: 2a5b3ac3-36f8-4345-ad5f-394634d924c2
async def analyze_file(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File to analyze"),
) -> None:
    """Analyze a single file for refactoring opportunities."""
    target_value = get_modularity_threshold()
    analyzer = RefactorAnalyzer()
    display = RefactorDisplay()
    recommender = RecommendationEngine()

    # Locate the file
    target_file = (settings.REPO_PATH / file_path).resolve()
    if not target_file.exists() or not target_file.is_file():
        display.console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Analyze file
    details = analyzer.analyze_file(target_file)

    if not details:
        display.show_clean_file()
        return

    # Display analysis
    display.show_file_analysis(file_path, details, target_value)

    # Show recommendations
    recommendations = recommender.generate(details)
    if recommendations:
        display.show_recommendations(recommendations)


@refactor_app.command("suggest")
@core_command(dangerous=False)
# ID: 3b5d6926-eb94-4ad8-994a-f5a0574f7da1
async def suggest_candidates(
    ctx: typer.Context,
    min_score: float = typer.Option(
        None, "--min-score", help="Filter by score (defaults to Constitution limit)"
    ),
    limit: int = typer.Option(10, "--limit", help="Number of files to show"),
) -> None:
    """Rank and suggest files that need refactoring based on current score."""
    target_value = get_modularity_threshold()
    filter_score = min_score if min_score is not None else target_value

    analyzer = RefactorAnalyzer()
    display = RefactorDisplay()

    display.console.print(
        f"[bold cyan]🔍 Scanning Codebase (Target Score: <{target_value})...[/bold cyan]\n"
    )

    # Scan codebase
    files = list(get_source_files())
    candidates = analyzer.scan_codebase(files, filter_score)

    if not candidates:
        display.show_no_candidates()
        return

    # Make paths relative for display
    for c in candidates:
        c["file"] = c["file"].relative_to(settings.REPO_PATH)

    display.show_candidates_table(candidates, target_value, limit)


@refactor_app.command("stats")
@core_command(dangerous=False)
# ID: dac13339-709c-4be9-9f64-9bd5bfaf1db9
async def show_stats(ctx: typer.Context) -> None:
    """Show aggregate codebase modularity health using Gaussian-derived risk tiers."""
    target_value = get_modularity_threshold()
    warning_level = target_value * 0.8

    analyzer = RefactorAnalyzer()
    display = RefactorDisplay()

    # Collect scores
    files = list(get_source_files())
    scores = analyzer.collect_scores(files)

    if not scores:
        display.console.print("[yellow]No Python files found for analysis.[/yellow]")
        return

    # Calculate statistics
    avg = sum(scores) / len(scores)
    high_risk_count = sum(1 for s in scores if s > target_value)
    warning_count = sum(1 for s in scores if warning_level < s <= target_value)
    healthy_count = len(scores) - high_risk_count - warning_count

    # Display statistics
    display.show_stats(
        total_files=len(scores),
        avg_score=avg,
        target_value=target_value,
        high_risk=high_risk_count,
        warning=warning_count,
        healthy=healthy_count,
    )


@refactor_app.command("score")
@core_command(dangerous=False)
# ID: 8b86cd83-5181-479d-aa80-6e98738841b6
async def check_file_score(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File path to analyze"),
) -> None:
    """
    Check the modularity score for a single file with detailed breakdown.

    Example:
        core-admin refactor score src/will/phases/canary_validation_phase.py
    """
    from rich.table import Table

    target_value = get_modularity_threshold()
    analyzer = RefactorAnalyzer()

    file = settings.REPO_PATH / file_path
    if not file.exists():
        RefactorDisplay.console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    details = analyzer.analyze_file(file)

    if not details:
        RefactorDisplay.console.print(
            f"[green]✅ {file_path} is below threshold ({target_value})[/green]"
        )
        return

    score = details["total_score"]

    # Display detailed breakdown
    table = Table(title=f"Modularity Score: {file_path}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Score", justify="right")

    table.add_row(
        "Responsibilities",
        str(details["responsibility_count"]),
        f"{details['breakdown']['responsibilities']:.1f}",
    )
    table.add_row(
        "Cohesion",
        f"{details['cohesion']:.2f}",
        f"{details['breakdown']['cohesion']:.1f}",
    )
    table.add_row(
        "Coupling (Concerns)",
        str(details["concern_count"]),
        f"{details['breakdown']['coupling']:.1f}",
    )
    table.add_row(
        "Size (LOC)",
        str(details["lines_of_code"]),
        f"{details['breakdown']['size']:.1f}",
    )
    table.add_row("", "", "")
    table.add_row("TOTAL", "", f"[bold]{score:.1f}/100[/bold]")
    table.add_row("Target", "", f"<{target_value}")

    RefactorDisplay.console.print(table)

    if score > target_value:
        RefactorDisplay.console.print(
            f"\n[red]❌ Exceeds threshold by {score - target_value:.1f} points[/red]"
        )
    else:
        RefactorDisplay.console.print("\n[yellow]⚠️  Within warning range[/yellow]")

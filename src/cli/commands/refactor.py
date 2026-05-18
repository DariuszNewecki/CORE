# src/cli/commands/refactor.py

"""Refactoring analysis commands.

Thin clients over /v1/refactor/{score,candidates,stats,threshold}
(ADR-057 D2). Display logic stays in `refactor_support.display`; data
fetching crosses the HTTP boundary via CoreApiClient.
"""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from api.cli import CoreApiClient
from cli.commands.refactor_support.display import RefactorDisplay
from cli.commands.refactor_support.display import console as refactor_console
from cli.commands.refactor_support.recommendations import RecommendationEngine
from cli.utils import core_command


logger = logging.getLogger(__name__)


_DEFAULT_CANDIDATE_LIMIT = 50


refactor_app = typer.Typer(
    help="Refactoring analysis and suggestions", no_args_is_help=True
)


@refactor_app.command("analyze")
@core_command(dangerous=False, requires_context=False)
# ID: 2a5b3ac3-36f8-4345-ad5f-394634d924c2
async def analyze_file(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File to analyze"),
) -> None:
    """Analyze a single file for refactoring opportunities."""
    _ = ctx
    client = CoreApiClient()
    threshold_payload = await client.refactor_threshold()
    target_value = float(threshold_payload.get("threshold", 60.0))

    display = RefactorDisplay()
    recommender = RecommendationEngine()

    try:
        score_payload = await client.refactor_score(file=file_path)
    except Exception as exc:
        display.console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc

    if not score_payload.get("found"):
        display.console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    details = score_payload.get("details")
    if not details:
        display.show_clean_file()
        return

    display.show_file_analysis(file_path, details, target_value)
    recommendations = recommender.generate(details)
    if recommendations:
        display.show_recommendations(recommendations)


@refactor_app.command("suggest")
@core_command(dangerous=False, requires_context=False)
# ID: 3b5d6926-eb94-4ad8-994a-f5a0574f7da1
async def suggest_candidates(
    ctx: typer.Context,
    min_score: float = typer.Option(
        None, "--min-score", help="Filter by score (defaults to constitutional limit)"
    ),
    limit: int = typer.Option(
        _DEFAULT_CANDIDATE_LIMIT, "--limit", help="Number of files to show"
    ),
) -> None:
    """Rank and suggest files that need refactoring based on current score."""
    _ = ctx
    client = CoreApiClient()
    threshold_payload = await client.refactor_threshold()
    target_value = float(threshold_payload.get("threshold", 60.0))
    display = RefactorDisplay()

    display.console.print(
        f"[bold cyan]🔍 Scanning Codebase (Target Score: <{target_value})...[/bold cyan]\n"
    )

    candidates_payload = await client.refactor_candidates(
        min_score=min_score, limit=limit
    )
    candidates = candidates_payload.get("candidates", [])

    if not candidates:
        display.show_no_candidates()
        return

    shaped = [
        {
            "file": c.get("file", ""),
            "score": float(c.get("score", 0.0)),
            "resp": int(c.get("responsibility_count", 0)),
            "loc": int(c.get("lines_of_code", 0)),
        }
        for c in candidates
    ]
    display.show_candidates_table(shaped, target_value, limit)


@refactor_app.command("stats")
@core_command(dangerous=False, requires_context=False)
# ID: dac13339-709c-4be9-9f64-9bd5bfaf1db9
async def show_stats(ctx: typer.Context) -> None:
    """Show aggregate codebase modularity health using risk tiers."""
    _ = ctx
    client = CoreApiClient()
    threshold_payload = await client.refactor_threshold()
    target_value = float(threshold_payload.get("threshold", 60.0))
    warning_level = target_value * 0.8

    stats = await client.refactor_stats()
    display = RefactorDisplay()

    if not stats.get("count"):
        display.console.print("[yellow]No Python files found for analysis.[/yellow]")
        return

    histogram = stats.get("histogram") or {}
    # Map five-bucket histogram onto the high_risk / warning / healthy tiers
    # that show_stats was built for.
    high_risk = sum(
        v for k, v in histogram.items() if _bucket_lower_bound(k) >= target_value
    )
    warning = sum(
        v
        for k, v in histogram.items()
        if warning_level <= _bucket_lower_bound(k) < target_value
    )
    healthy = stats["count"] - high_risk - warning

    display.show_stats(
        total_files=stats["count"],
        avg_score=float(stats.get("mean", 0.0)),
        target_value=target_value,
        high_risk=high_risk,
        warning=warning,
        healthy=healthy,
    )


@refactor_app.command("score")
@core_command(dangerous=False, requires_context=False)
# ID: 8b86cd83-5181-479d-aa80-6e98738841b6
async def check_file_score(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File path to analyze"),
) -> None:
    """Check the modularity score for a single file with detailed breakdown."""
    _ = ctx
    client = CoreApiClient()
    threshold_payload = await client.refactor_threshold()
    target_value = float(threshold_payload.get("threshold", 60.0))

    try:
        payload = await client.refactor_score(file=file_path)
    except Exception as exc:
        RefactorDisplay.console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc

    if not payload.get("found"):
        RefactorDisplay.console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    details = payload.get("details")
    if not details:
        RefactorDisplay.console.print(
            f"[green]✅ {file_path} is below threshold ({target_value})[/green]"
        )
        return

    score = float(details["total_score"])
    table = Table(title=f"Modularity Score: {file_path}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Score", justify="right")

    breakdown = details.get("breakdown", {})
    table.add_row(
        "Responsibilities",
        str(details.get("responsibility_count", 0)),
        f"{breakdown.get('responsibilities', 0):.1f}",
    )
    table.add_row(
        "Cohesion",
        f"{details.get('cohesion', 0):.2f}",
        f"{breakdown.get('cohesion', 0):.1f}",
    )
    table.add_row(
        "Coupling (Concerns)",
        str(details.get("concern_count", 0)),
        f"{breakdown.get('coupling', 0):.1f}",
    )
    table.add_row(
        "Size (LOC)",
        str(details.get("lines_of_code", 0)),
        f"{breakdown.get('size', 0):.1f}",
    )
    table.add_row("", "", "")
    table.add_row("TOTAL", "", f"[bold]{score:.1f}/100[/bold]")
    table.add_row("Target", "", f"<{target_value}")
    refactor_console.print(table)

    if score > target_value:
        RefactorDisplay.console.print(
            f"\n[red]❌ Exceeds threshold by {score - target_value:.1f} points[/red]"
        )
    else:
        refactor_console.print("\n[yellow]⚠️  Within warning range[/yellow]")


def _bucket_lower_bound(bucket: str) -> float:
    """Return the lower bound implied by a histogram bucket key."""
    if bucket == "80+":
        return 80.0
    try:
        return float(bucket.split("-", 1)[0])
    except (ValueError, IndexError):
        return 0.0
